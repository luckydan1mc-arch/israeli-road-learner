"""Street-name anchors for the offline basemap: [name, lat, lon, angle, class] every ~450 m along each named street."""
import json, math, sys, collections
import osmium
from shapely.geometry import LineString
from shapely.ops import linemerge

PBF, OUT = sys.argv[1], sys.argv[2]
CLASS = {"primary": 2, "primary_link": 2, "secondary": 3, "secondary_link": 3, "tertiary": 4, "tertiary_link": 4,
         "unclassified": 5, "residential": 5, "living_street": 5}
KX = math.cos(math.radians(31.7))

class H(osmium.SimpleHandler):
    def __init__(s): super().__init__(); s.by = collections.defaultdict(list)
    def way(s, w):
        c = CLASS.get(w.tags.get("highway"))
        if c is None: return
        nm = (w.tags.get("name:he") or w.tags.get("name") or "").strip()
        if not nm or len(nm) > 32: return
        try: pts = [(n.lon, n.lat) for n in w.nodes]
        except osmium.InvalidLocationError: return
        if len(pts) >= 2: s.by[nm].append((c, LineString(pts)))
h = H(); h.apply_file(PBF, locations=True, idx="flex_mem")
print("names", len(h.by), flush=True)

def metres(l):   # approximate length in metres
    cs = list(l.coords)
    return sum(math.hypot((b[0] - a[0]) * KX, b[1] - a[1]) for a, b in zip(cs, cs[1:])) * 111320

anchors = []
for nm, items in h.by.items():
    c = min(c for c, _ in items)
    merged = linemerge([l for _, l in items])
    parts = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    for l in parts:
        L = metres(l)
        if L < 70: continue
        n = max(1, int(L // 450))
        for k in range(n):
            f = (k + .5) / n
            p = l.interpolate(f, normalized=True)
            a = l.interpolate(max(0, f - 15 / L), normalized=True); b = l.interpolate(min(1, f + 15 / L), normalized=True)
            ang = math.degrees(math.atan2(-(b.y - a.y), (b.x - a.x) * KX))   # screen angle (y down)
            if ang > 90: ang -= 180
            if ang < -90: ang += 180
            anchors.append([nm, round(p.y, 5), round(p.x, 5), round(ang), c])
print("anchors", len(anchors), collections.Counter(a[4] for a in anchors), flush=True)
json.dump(anchors, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
