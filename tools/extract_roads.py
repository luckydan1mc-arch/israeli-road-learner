"""Extract every numbered road in Israel (incl. Judea/Samaria & Golan) from an OSM PBF.
Output: roads.json  {ref: {"g":[[ [lat,lon],... ], ...], "names":[...], "hw":"motorway", "km":123.4}}
Geometry is merged into continuous polylines and lightly simplified (~3 m tolerance).
"""
import json, re, sys, math, collections
import osmium
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import linemerge

PBF = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else "roads.json"

ROAD_HW = {"motorway","trunk","primary","secondary","tertiary","unclassified","residential",
           "motorway_link","trunk_link","primary_link","secondary_link","tertiary_link",
           "road","living_street"}
REF_OK = re.compile(r"^[1-9]\d{0,3}$")
HEB = re.compile(r"[֐-׿]")
RANK = {"motorway":0,"trunk":1,"primary":2,"secondary":3,"tertiary":4,"unclassified":5,"residential":6,
        "road":7,"living_street":7,"service":8,"track":9}

# --- pass 1: national borders of IL to filter out Jordan/Lebanon/Egypt/Syria roads ---
class Areas(osmium.SimpleHandler):
    def __init__(s):
        super().__init__(); s.polys = []
    def area(s, a):
        t = a.tags
        if (not a.from_way()) and a.orig_id() in (1473946, 1613659, 1803010, 16119376):
            from shapely.geometry import Polygon, MultiPolygon
            ps = []
            for outer in a.outer_rings():
                o = [(n.lon, n.lat) for n in outer]
                inner = [[(n.lon, n.lat) for n in r] for r in a.inner_rings(outer)]
                ps.append(Polygon(o, inner))
            s.polys.append(MultiPolygon(ps).buffer(0))

class Ways(osmium.SimpleHandler):
    def __init__(s):
        super().__init__()
        s.segs = collections.defaultdict(list)
        s.names = collections.defaultdict(collections.Counter)
        s.hw = collections.defaultdict(collections.Counter)
    def way(s, w):
        hw = w.tags.get("highway")
        ref = w.tags.get("ref")
        if not hw or not ref:
            return
        if w.tags.get("piste:type") or w.tags.get("route") == "piste" or w.tags.get("access") in ("private", "no"):
            return
        base = hw if hw in ROAD_HW else None
        if base is None:
            return
        try:
            pts = [(n.lat, n.lon) for n in w.nodes]
        except osmium.InvalidLocationError:
            return
        if len(pts) < 2:
            return
        nm = w.tags.get("name:he") or w.tags.get("name") or ""
        for r in re.split(r"[;,]", ref):
            r = r.strip()
            if REF_OK.match(r):
                s.segs[r].append((pts, bool(HEB.search(nm)) or bool(HEB.search(w.tags.get("name", "")))))
                if nm and HEB.search(nm):
                    s.names[r][nm] += 1
                s.hw[r][hw.replace("_link", "")] += 1

print("pass 1: borders", flush=True)
A = Areas(); A.apply_file(PBF, locations=True, idx="flex_mem")
from shapely.ops import unary_union
from shapely.prepared import prep
border = unary_union(A.polys) if A.polys else None
# Golan is not inside IL boundary in OSM in some versions; add an explicit box
from shapely.geometry import box
region = border.buffer(0.002)
pr = prep(region)
print("  border polys:", len(A.polys), flush=True)

print("pass 2: ways", flush=True)
W = Ways(); W.apply_file(PBF, locations=True, idx="flex_mem")
print("  refs:", len(W.segs), flush=True)

def km(line):
    d = 0
    for (a1, o1), (a2, o2) in zip(line, line[1:]):
        dx = (o2 - o1) * 111.32 * math.cos(math.radians((a1 + a2) / 2)); dy = (a2 - a1) * 110.57
        d += math.hypot(dx, dy)
    return d

out = {}
for ref, segs in W.segs.items():
    keep = []
    for pts, heb in segs:
        mid = pts[len(pts) // 2]
        inside = pr.contains(Point(mid[1], mid[0]))
        if inside:
            keep.append(pts)
    if not keep:
        continue
    merged = linemerge(MultiLineString([LineString([(lo, la) for la, lo in p]) for p in keep]))
    geoms = list(merged.geoms) if merged.geom_type == "MultiLineString" else [merged]
    lines = []
    total = 0
    for g in geoms:
        g2 = g.simplify(0.00003, preserve_topology=False)
        coords = [[round(la, 5), round(lo, 5)] for lo, la in g2.coords]
        if len(coords) >= 2:
            lines.append(coords); total += km([(la, lo) for lo, la in g.coords])
    if total < 0.15:
        continue
    hwc = W.hw[ref]
    best_hw = min(hwc, key=lambda h: RANK.get(h, 9)) if hwc else "road"
    out[ref] = {"g": lines, "names": [n for n, _ in W.names[ref].most_common(4)], "hw": best_hw, "km": round(total, 1)}

json.dump(out, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
d = collections.Counter(len(k) for k in out)
print("roads:", len(out), dict(sorted(d.items())), flush=True)
