"""Settlements for the "guess the settlement" quiz.

usage: settlements.py <osm.pbf> roads_min.json regions.json out.json

Takes OSM place nodes (city, town, village, hamlet) with a Hebrew name that lie in one of the app's regions.
Inside the West Bank only places whose main OSM name is Hebrew are kept (Israeli localities); Gaza is left out.
Each record: [name, size, lat, lon, regions, councils, nearby roads]
  size 0 = city or town (place=city/town), 1 = village or hamlet
  nearby roads = numbered roads of up to 3 digits passing within 1 km (2 km for a city/town), nearest first
"""
import json, re, sys
import osmium
from shapely import wkb
from shapely.geometry import Point, Polygon, MultiPolygon, LineString
from shapely.strtree import STRtree

PBF, ROADS, REGIONS, OUT = sys.argv[1:5]
WEST_BANK, GAZA = 1613659, 1473938
KIND = {"city": 0, "town": 0, "village": 1, "hamlet": 1}
HEB = re.compile("[א-ת]")

places, outside = [], {}
fac = osmium.geom.WKBFactory()


class H(osmium.SimpleHandler):
    def node(self, n):
        k = KIND.get(n.tags.get("place"))
        if k is None: return
        he = (n.tags.get("name:he") or "").strip()
        nm = (n.tags.get("name") or "").strip()
        if not he and HEB.search(nm): he = nm
        if not he or not HEB.search(he): return
        try: pop = int(re.sub(r"\D", "", n.tags.get("population", "") or "0") or 0)
        except ValueError: pop = 0
        places.append({"he": he, "k": k, "lat": n.location.lat, "lon": n.location.lon,
                       "hebmain": bool(HEB.search(nm)), "pop": pop})

    def area(self, a):
        if a.from_way(): return
        if a.orig_id() in (WEST_BANK, GAZA):
            outside[a.orig_id()] = wkb.loads(fac.create_multipolygon(a), hex=True)


H().apply_file(PBF, locations=True, idx="flex_mem")
assert WEST_BANK in outside and GAZA in outside, outside.keys()
wb, gaza = outside[WEST_BANK].buffer(0), outside[GAZA].buffer(0)

RG = json.load(open(REGIONS, encoding="utf-8"))


class Rings:   # region outlines are flat lists of rings (outer parts and holes), filled even-odd like on the map
    def __init__(self, rings):
        self.ps = [Polygon([(x, y) for y, x in r]).buffer(0) for r in rings if len(r) >= 4]
    def contains(self, pt):
        return sum(p.contains(pt) for p in self.ps) % 2 == 1


reg = [Rings(r["o"]) for r in RG["regions"]]
cou = [Rings(c["o"]) for c in RG["councils"]]

roads = json.load(open(ROADS, encoding="utf-8"))
KM = (94.0, 110.0)   # degrees -> km (lon, lat) around 31.5N
rl, rn = [], []
for n, r in roads.items():
    if len(n) > 3: continue
    for g in r["g"]:
        if len(g) < 2: continue
        rl.append(LineString([(x * KM[0], y * KM[1]) for y, x in g])); rn.append(int(n))
tree = STRtree(rl)

out, seen = [], []
for p in sorted(places, key=lambda p: (p["k"], -p["pop"])):
    pt = Point(p["lon"], p["lat"])
    if gaza.contains(pt): continue
    if wb.contains(pt) and not p["hebmain"]: continue
    R = [i for i, g in enumerate(reg) if g.contains(pt)]
    if not R: continue
    if any(s[0] == p["he"] and abs(s[1] - p["lat"]) < 0.05 and abs(s[2] - p["lon"]) < 0.05 for s in seen): continue
    seen.append((p["he"], p["lat"], p["lon"]))
    C = [i for i, g in enumerate(cou) if g.contains(pt)]
    q = Point(p["lon"] * KM[0], p["lat"] * KM[1]); lim = 2.0 if p["k"] == 0 else 1.0
    best = {}
    for i in tree.query(q.buffer(lim)):
        d = rl[i].distance(q)
        if d <= lim and d < best.get(rn[i], 9e9): best[rn[i]] = d
    near = [n for n, _ in sorted(best.items(), key=lambda kv: kv[1])][:4]
    out.append([p["he"], p["k"], round(p["lat"], 5), round(p["lon"], 5), R, C, near])

json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(len(out), "settlements;", sum(1 for s in out if s[1] == 0), "cities/towns")
