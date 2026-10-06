"""Offline basemap for Israeli Road Learner, built from the OSM extract.

Output: basemap.json with
  roads[c]   : list of linestrings (lat,lon) per road class c (0 motorway .. 5 minor)
  built      : built-up polygons      green: parks/forest polygons
  water      : lakes/reservoirs       sea:   sea polygon (from natural=coastline)
  border     : country border lines   places: [name, kind, lat, lon, pop]
  wlabels    : [name, lat, lon] for big lakes
"""
import json, math, sys, collections
import osmium
import shapely
from shapely import wkb
from shapely.geometry import LineString, Polygon, MultiPolygon, box, Point
from shapely.ops import linemerge, unary_union, polygonize

PBF = sys.argv[1]
OUT = sys.argv[2]
M = 1 / 111320.0                      # metres -> degrees (lat)
BBOX = (27.5, 27.0, 39.5, 37.5)       # lon0, lat0, lon1, lat1 (frame for the sea polygon)

CLASS = {"motorway": 0, "motorway_link": 0, "trunk": 1, "trunk_link": 1,
         "primary": 2, "primary_link": 2, "secondary": 3, "secondary_link": 3,
         "tertiary": 4, "tertiary_link": 4,
         "unclassified": 5, "residential": 5, "living_street": 5, "road": 5}
TOL = {0: 2, 1: 2, 2: 2, 3: 2.5, 4: 3, 5: 4}          # simplification tolerance (m)
PLACE_KINDS = {"city": 0, "town": 1, "village": 2, "hamlet": 3, "suburb": 4, "quarter": 5, "neighbourhood": 5}
BUILT = {"residential", "commercial", "retail", "industrial"}
WATER_LU = {"reservoir", "basin", "salt_pond"}

# ---------- pass 1: relation members of country borders ----------
class Rel(osmium.SimpleHandler):
    def __init__(s):
        super().__init__(); s.border_ways = set()
    def relation(s, r):
        t = r.tags
        if t.get("boundary") == "administrative" and t.get("admin_level") == "2":
            for m in r.members:
                if m.type == "w": s.border_ways.add(m.ref)
rel = Rel(); rel.apply_file(PBF)
print("border ways", len(rel.border_ways), flush=True)

# ---------- pass 2: ways (roads, coastline, borders) + place nodes ----------
class W(osmium.SimpleHandler):
    def __init__(s):
        super().__init__()
        s.roads = collections.defaultdict(list); s.coast = []; s.border = []; s.places = []
    def node(s, n):
        k = n.tags.get("place")
        if k in PLACE_KINDS:
            nm = n.tags.get("name:he") or n.tags.get("name")
            if not nm: return
            try: pop = int(str(n.tags.get("population", "0")).replace(",", "").split(".")[0] or 0)
            except ValueError: pop = 0
            s.places.append([nm, PLACE_KINDS[k], round(n.location.lat, 5), round(n.location.lon, 5), pop])
    def way(s, w):
        t = w.tags
        c = CLASS.get(t.get("highway"))
        isc = t.get("natural") == "coastline"
        isb = w.id in rel.border_ways
        if c is None and not isc and not isb: return
        if t.get("area") == "yes": return
        try: pts = [(n.lon, n.lat) for n in w.nodes]
        except osmium.InvalidLocationError: return
        if len(pts) < 2: return
        if c is not None: s.roads[c].append(LineString(pts))
        if isc: s.coast.append(LineString(pts))
        if isb: s.border.append(LineString(pts))
wh = W(); wh.apply_file(PBF, locations=True, idx="flex_mem")
print("roads", {c: len(v) for c, v in wh.roads.items()}, "coast", len(wh.coast), "border", len(wh.border), "places", len(wh.places), flush=True)

# ---------- pass 3: areas (built-up, water, green) ----------
wkbf = osmium.geom.WKBFactory()
class A(osmium.SimpleHandler):
    def __init__(s):
        super().__init__(); s.built = []; s.water = []; s.green = []
    def area(s, a):
        t = a.tags
        lu = t.get("landuse"); nat = t.get("natural"); lei = t.get("leisure")
        kind = None
        if lu in BUILT: kind = "built"
        elif nat == "water" or lu in WATER_LU: kind = "water"
        elif lu == "forest" or nat == "wood" or lei in ("park", "nature_reserve") or lu in ("grass", "recreation_ground"): kind = "green"
        if not kind: return
        try: g = wkb.loads(wkbf.create_multipolygon(a), hex=True)
        except Exception: return
        if not g.is_valid: g = g.buffer(0)
        name = t.get("name:he") or t.get("name") or ""
        getattr(s, kind).append((g, name))
ah = A(); ah.apply_file(PBF, locations=True, idx="flex_mem")
print("areas built", len(ah.built), "water", len(ah.water), "green", len(ah.green), flush=True)

def area_m2(g):
    lat = g.centroid.y
    return g.area * (111320 ** 2) * math.cos(math.radians(lat))

def polys(g):
    if g.is_empty: return []
    if isinstance(g, Polygon): return [g]
    if isinstance(g, MultiPolygon): return list(g.geoms)
    return [p for p in getattr(g, "geoms", []) if isinstance(p, Polygon)]

def ring_coords(r):
    return [[round(y, 5), round(x, 5)] for x, y in r.coords]

def poly_out(geoms, tol_m, min_m2):
    out = []
    for g in geoms:
        g = g.simplify(tol_m * M, preserve_topology=True)
        for p in polys(g):
            if area_m2(p) < min_m2: continue
            rings = [ring_coords(p.exterior)] + [ring_coords(i) for i in p.interiors if area_m2(Polygon(i)) >= min_m2]
            if len(rings[0]) >= 4: out.append(rings)
    return out

# ---------- roads: merge per class, simplify ----------
roads_out = {}
for c in sorted(wh.roads):
    merged = linemerge(unary_union(wh.roads[c])) if c < 5 else linemerge(wh.roads[c])
    geoms = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    lines = []
    for g in geoms:
        g = g.simplify(TOL[c] * M, preserve_topology=False)
        cs = [[round(y, 5), round(x, 5)] for x, y in g.coords]
        if len(cs) >= 2: lines.append(cs)
    roads_out[c] = lines
    print("class", c, "lines", len(lines), "pts", sum(len(l) for l in lines), flush=True)

# ---------- built-up: union neighbouring blocks, then simplify ----------
built_u = unary_union([g for g, _ in ah.built])
built_out = poly_out(polys(built_u), 8, 4000)
print("built polys", len(built_out), "pts", sum(len(r) for p in built_out for r in p), flush=True)

green_u = unary_union([g for g, _ in ah.green if area_m2(g) > 20000])
green_out = poly_out(polys(green_u), 15, 30000)
print("green polys", len(green_out), "pts", sum(len(r) for p in green_out for r in p), flush=True)

water_out, wlabels = [], []
for g, nm in ah.water:
    a = area_m2(g)
    if a < 15000: continue
    water_out += poly_out([g], 6, 15000)
    if nm and a > 1.5e6:
        c = g.representative_point(); wlabels.append([nm, round(c.y, 4), round(c.x, 4), round(a)])
print("water polys", len(water_out), "labels", len(wlabels), flush=True)

# ---------- sea from the coastline (see sea.py) ----------
from sea import build_sea
sea, votes = build_sea([l for l in (linemerge(wh.coast).geoms if hasattr(linemerge(wh.coast), "geoms") else [linemerge(wh.coast)])], BBOX)
sea_out = poly_out(polys(sea), 10, 1e5)
print("sea face votes", votes, "sea polys", len(sea_out), flush=True)

# ---------- borders ----------
bm = linemerge(wh.border)
bm = list(bm.geoms) if hasattr(bm, "geoms") else [bm]
border_out = []
sea_buf = sea.buffer(0.003)
for g0 in bm:
  for g in (lambda d: list(d.geoms) if hasattr(d, "geoms") else [d])(g0.difference(sea_buf)):
    if g.is_empty or g.length < 0.002: continue
    g = g.simplify(15 * M)
    border_out.append([[round(y, 5), round(x, 5)] for x, y in g.coords])

# ---------- places: drop exact duplicates, biggest first ----------
seen, places = set(), []
for p in sorted(wh.places, key=lambda p: (p[1], -p[4])):
    key = (p[0], round(p[2], 2), round(p[3], 2))
    if key in seen: continue
    seen.add(key); places.append(p)
print("places kept", len(places), collections.Counter(p[1] for p in places), flush=True)

json.dump({"roads": roads_out, "built": built_out, "green": green_out, "water": water_out, "wlabels": wlabels,
           "sea": sea_out, "border": border_out, "places": places}, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
print("done")
