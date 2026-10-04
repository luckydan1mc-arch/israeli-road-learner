"""Add from/to/via/dir/region to roads.json using place nodes from the PBF."""
import json, sys, math
import osmium
from shapely.geometry import Point, LineString, MultiLineString
from shapely.strtree import STRtree

PBF, IN, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
KIND_RANK = {"city": 0, "town": 1, "village": 2, "suburb": 3, "hamlet": 4, "isolated_dwelling": 5}

class Places(osmium.SimpleHandler):
    def __init__(s):
        super().__init__(); s.p = []
    def node(s, n):
        pl = n.tags.get("place")
        if pl in KIND_RANK:
            he = n.tags.get("name:he")
            if not he:
                nm = n.tags.get("name", "")
                he = nm if any("֐" <= c <= "׿" for c in nm) else None
            if he:
                s.p.append((he, pl, n.location.lat, n.location.lon))

class Areas(osmium.SimpleHandler):
    def __init__(s):
        super().__init__(); s.polys = []
    def area(s, a):
        if (not a.from_way()) and a.orig_id() in (1473946, 1613659, 1803010, 16119376):
            from shapely.geometry import Polygon, MultiPolygon
            ps = []
            for outer in a.outer_rings():
                ps.append(Polygon([(n.lon, n.lat) for n in outer], [[(n.lon, n.lat) for n in r] for r in a.inner_rings(outer)]))
            s.polys.append(MultiPolygon(ps).buffer(0))
from shapely.ops import unary_union
from shapely.prepared import prep
AR = Areas(); AR.apply_file(PBF, locations=True, idx="flex_mem")
REG = prep(unary_union(AR.polys).buffer(0.001))
P = Places(); P.apply_file(PBF)
places = [p for p in P.p if p[1] != "suburb" and REG.contains(Point(p[3], p[2]))]
print("places", len(places))
KX = math.cos(math.radians(31.7))  # lon scale
geoms = [Point(p[3] * KX, p[2]) for p in places]
tree = STRtree(geoms)

def nearest_place(lat, lon, maxkm, prefer_big=True):
    pt = Point(lon * KX, lat)
    idx = tree.query(pt.buffer(maxkm / 111))
    best = None
    for i in idx:
        d = geoms[i].distance(pt) * 111
        rank = KIND_RANK[places[i][1]]
        score = d + ({0: 0, 1: 1.5, 2: 4, 3: 6, 4: 7, 5: 8}[rank] if prefer_big else 0)
        if best is None or score < best[0]:
            best = (score, i, d)
    return places[best[1]] if best else None

def region_of(lat, lon):
    if lat >= 32.45: return "north"
    if lat < 31.45: return "south"
    if lon >= 35.05 or 31.6 <= lat < 31.9: return "jlm"
    if lat >= 31.9: return "center"
    return "south"

d = json.load(open(IN))
for ref, r in d.items():
    pts = [p for l in r["g"] for p in l]
    # farthest pair among component endpoints (+ samples) for start/end
    cands = [l[0] for l in r["g"]] + [l[-1] for l in r["g"]]
    step = max(1, len(pts) // 250)
    cands = cands[:300] + pts[::step]
    def dist(a, b): return math.hypot((a[0] - b[0]) * 110.6, (a[1] - b[1]) * 94.6)
    best = (0, cands[0], cands[-1])
    for i in range(len(cands)):
        for j in range(i + 1, len(cands)):
            dd = dist(cands[i], cands[j])
            if dd > best[0]: best = (dd, cands[i], cands[j])
    span, a, b = best
    # order: north->south for N-S roads, west->east for E-W roads
    ns = abs(a[0] - b[0]) * 110.6 >= abs(a[1] - b[1]) * 94.6
    if ns and a[0] < b[0]: a, b = b, a
    if not ns and a[1] > b[1]: a, b = b, a
    r["dir"] = "NS" if int(ref) % 2 == 0 else "EW"
    r["geo"] = "NS" if ns else "EW"
    r["span"] = round(span, 1)
    near = min(10, max(2.5, span / 4))
    fa = nearest_place(a[0], a[1], near); fb = nearest_place(b[0], b[1], near)
    r["from"] = fa[0] if fa else ""; r["to"] = fb[0] if fb else ""
    r["a"] = a; r["b"] = b
    # via: places within ~1.2 km of the road, ordered along a->b
    ml = MultiLineString([LineString([(p[1] * KX, p[0]) for p in l]) for l in r["g"]])
    idx = tree.query(ml.buffer(3 / 111))
    via = []
    ax, ay = a[1] * KX, a[0]
    for i in idx:
        lim = 3 if places[i][1] in ("city", "town") else 1.0
        if geoms[i].distance(ml) * 111 <= lim:
            pl = places[i]
            via.append((KIND_RANK[pl[1]], math.hypot(pl[3] * KX - ax, pl[2] - ay), pl[0]))
    # keep the biggest places, then sort along the road
    via.sort()
    chosen = via[:7]
    chosen.sort(key=lambda v: v[1])
    names = []
    for v in chosen:
        if v[2] not in names and v[2] not in (r["from"], r["to"]): names.append(v[2])
    if not names:   # short roads: fall back to the closest villages within 2 km
        near2 = sorted((geoms[i].distance(ml) * 111, places[i][0]) for i in tree.query(ml.buffer(2 / 111)))
        for dkm, nm in near2:
            if dkm <= 2 and nm not in names and nm not in (r["from"], r["to"]): names.append(nm)
            if len(names) >= 3: break
    r["via"] = names
    regs = set(region_of(p[0], p[1]) for p in pts[:: max(1, len(pts) // 60)])
    r["reg"] = sorted(regs)
    r.pop("km", None)

json.dump(d, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
for k in ["1", "6", "38", "90", "443", "3866", "375", "65"]:
    x = d[k]; print(k, x["dir"], x["from"], "->", x["to"], "|", " · ".join(x["via"]), x["reg"])
