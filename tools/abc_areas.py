"""Areas A, B and C (Oslo II) of the West Bank, for the map layer.

usage: abc_areas.py <osm.pbf> out.json
Reads the OSM boundary relations "Area A" (3791783), "Area B" (3791784), "Area C" (3791785),
simplifies them (~30 m), drops slivers under 0.02 km2, and writes
{"A": [[outer, hole, ...], ...], "B": [...], "C": [...]} with [lat, lon] points.
"""
import json, sys
import osmium
from shapely import wkb
from shapely.geometry import Polygon, MultiPolygon

PBF, OUT = sys.argv[1:3]
IDS = {3791783: "A", 3791784: "B", 3791785: "C"}
fac = osmium.geom.WKBFactory()
geo = {}


class H(osmium.SimpleHandler):
    def area(self, a):
        if not a.from_way() and a.orig_id() in IDS:
            geo[IDS[a.orig_id()]] = wkb.loads(fac.create_multipolygon(a), hex=True)


H().apply_file(PBF, locations=True, idx="flex_mem")
assert set(geo) == {"A", "B", "C"}, geo.keys()

KM2 = 110 * 94
ring = lambda r: [[round(y, 5), round(x, 5)] for x, y in r.coords]
out = {}
for k, g in sorted(geo.items()):
    g = g.buffer(0).simplify(0.0003, preserve_topology=True)
    parts = list(g.geoms) if isinstance(g, MultiPolygon) else [g]
    polys = []
    for p in parts:
        if not isinstance(p, Polygon) or p.area * KM2 < 0.02: continue
        polys.append([ring(p.exterior)] + [ring(h) for h in p.interiors if Polygon(h).area * KM2 >= 0.02])
    out[k] = polys
    print(k, len(polys), "polygons,", sum(len(r) for p in polys for r in p), "points")
json.dump(out, open(OUT, "w", encoding="utf-8"), separators=(",", ":"))
