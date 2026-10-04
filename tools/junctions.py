"""Extract named junctions (צומת) and interchanges (מחלף) and the numbered roads that meet at each.
Writes junctions.json: [{"n": name, "k": "j"|"i", "p": [lat, lon], "r": [road numbers]}]
"""
import json, math, sys, collections, re
import osmium
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

PBF, ROADS_JSON, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
KX = math.cos(math.radians(31.7))
OK_TAGS = {"motorway_junction", "traffic_signals", "crossing", "yes", "stop", "give_way", "mini_roundabout", "turning_circle"}

class N(osmium.SimpleHandler):
    def __init__(s): super().__init__(); s.pts = []
    def node(s, n):
        t = n.tags
        nm = (t.get("name:he") or t.get("name") or "").strip()
        if t.get("highway") == "motorway_junction" and nm and not nm.startswith(("צומת ", "מחלף ")) and any("\u0590" <= ch <= "\u05FF" for ch in nm):
            nm = "מחלף " + nm
        if not (nm.startswith("צומת ") or nm.startswith("מחלף ")): return
        if t.get("highway") in ("bus_stop", "platform", "proposed", "construction") or t.get("public_transport") or t.get("railway"): return
        kind = t.get("highway") or t.get("junction") or ""
        if kind and kind not in OK_TAGS and t.get("junction") is None: return
        # names like "מחלף X למזרח" / "מחלף X - יציאה" describe a ramp: keep the base name
        base = re.split(r"\s+(?:ל(?:מזרח|מערב|צפון|דרום)|-|–|יציאה|כניסה)\b", nm)[0].strip()
        s.pts.append((base, n.location.lat, n.location.lon))

    def way(s, w):
        # junctions mapped as a named road piece / roundabout
        t = w.tags; nm = (t.get("name:he") or t.get("name") or "").strip()
        if not (nm.startswith("צומת ") or nm.startswith("מחלף ")) or not (t.get("highway") or t.get("junction")): return
        if t.get("highway") in ("bus_stop", "platform", "proposed", "construction"): return
        try: pts = [(n.lat, n.lon) for n in w.nodes]
        except osmium.InvalidLocationError: return
        if pts: s.pts.append((nm, sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)))

H = N(); H.apply_file(PBF, locations=True, idx="flex_mem")
print("named nodes", len(H.pts))

# merge nodes with the same name that lie within ~2 km of each other
groups = collections.defaultdict(list)
for nm, la, lo in H.pts: groups[nm].append((la, lo))
junctions = []
for nm, pts in groups.items():
    clusters = []
    for p in pts:
        for c in clusters:
            if math.hypot((c[0][0] - p[0]) * 110.6, (c[0][1] - p[1]) * 110.6 * KX) < (3.5 if nm.startswith("מחלף") else 1.5): c.append(p); break
        else: clusters.append([p])
    for c in clusters:
        la = sum(x[0] for x in c) / len(c); lo = sum(x[1] for x in c) / len(c)
        junctions.append({"n": nm, "k": "i" if nm.startswith("מחלף") else "j", "p": [round(la, 5), round(lo, 5)], "_pts": c})
print("junctions after merge", len(junctions))

roads = json.load(open(ROADS_JSON))
lines, owner = [], []
for ref, r in roads.items():
    for l in r["g"]:
        if len(l) >= 2:
            lines.append(LineString([(p[1] * KX, p[0]) for p in l])); owner.append(int(ref))
tree = STRtree(lines)
out = []
for j in junctions:
    rad = (0.3 if j["k"] == "i" else 0.15) / 110.6        # checked around every node of the junction/interchange
    near = set()
    for la, lo in j.pop("_pts"):
        pt = Point(lo * KX, la)
        near |= {owner[i] for i in tree.query(pt.buffer(rad)) if lines[i].distance(pt) <= rad}
    near = sorted(near)
    if not near: continue
    j["r"] = near
    out.append(j)
# a "junction" name that repeats many times is a business (e.g. the bookshop chain "צומת ספרים"), not a place
cnt = collections.Counter(j["n"] for j in out)
out = [j for j in out if cnt[j["n"]] <= 3]
# same name twice (e.g. two different "צומת הכפר"): keep both, they differ by place
print("junctions on numbered roads", len(out), "| interchanges", sum(1 for j in out if j["k"] == "i"),
      "| 2+ roads", sum(1 for j in out if len(j["r"]) >= 2))
json.dump(out, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
for nm in ["מחלף גלילות", "מחלף גלילות צפון", "מחלף השבעה", "צומת גומא", "מחלף נחשונים", "מחלף בן שמן", "צומת גולני", "מחלף שער הגיא", "צומת בית קמה", "מחלף לטרון", "צומת הערבה", "צומת מגידו", "מחלף קסם"]:
    print(nm, [j["r"] for j in out if j["n"] == nm])
