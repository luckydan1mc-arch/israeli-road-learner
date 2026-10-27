"""Sanity checks on the road data. usage: audit_roads.py roads_min.json regions.json settlements.json [basemap.json]
(pass the offline basemap.json too, for its full list of places: settlements.json leaves out West Bank
Palestinian villages, so names like "עראבה" would otherwise only match their namesake in the Galilee)
Prints:
  - pieces of a 3/4-digit road outside the latitude band of its numbering zone (first digit = zone, south to north)
  - stray pieces (< 2 km, > 3 km from the rest of the road) left after prune_fragments.py
  - endpoint / via names more than 6 / 4 km from the road
  - junctions naming a road that is not in the data, roads with no region
"""
import json, math, sys, collections
d = json.load(open(sys.argv[1], encoding="utf-8")); R = json.load(open(sys.argv[2], encoding="utf-8"))
S = json.load(open(sys.argv[3], encoding="utf-8"))
km = lambda a, b: math.hypot((a[0] - b[0]) * 110, (a[1] - b[1]) * 94)
L = lambda l: sum(km(l[i], l[i + 1]) for i in range(len(l) - 1))
med = collections.defaultdict(list)
for n, r in d.items():
    if len(n) >= 3:
        pts = sorted(p for l in r["g"] for p in l); med[n[0]].append(pts[len(pts) // 2][0])
band = {z: (sorted(v)[int(.03 * (len(v) - 1))] - .2, sorted(v)[int(.97 * (len(v) - 1))] + .2) for z, v in med.items()}
print("== outside numbering zone")
for n, r in d.items():
    if len(n) >= 3:
        lo, hi = band[n[0]]; bad = [l for l in r["g"] if not any(lo <= p[0] <= hi for p in l)]
        if bad: print(" ", n, round(sum(L(l) for l in bad), 1), "km of", round(sum(L(l) for l in r["g"]), 1), r["f"], "–", r["t"])
print("== stray pieces")
for n, r in d.items():
    g = r["g"]; N = len(g); par = list(range(N))
    def f(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    Sm = [l[::max(1, len(l) // 20)] + [l[-1]] for l in g]
    for i in range(N):
        for j in range(i + 1, N):
            if f(i) != f(j) and any(km(a, b) < 3 for a in Sm[i] for b in Sm[j]): par[f(i)] = f(j)
    comps = {}
    for i in range(N): comps.setdefault(f(i), []).append(i)
    cl = sorted(comps.values(), key=lambda c: -sum(L(g[i]) for i in c))
    for c in cl[1:]:
        ln = sum(L(g[i]) for i in c); gap = min(km(a, b) for i in c for j in cl[0] for a in Sm[i] for b in Sm[j])
        if ln < 2 and gap > 3: print(" ", n, round(ln, 1), "km,", round(gap, 1), "km away")
pos = collections.defaultdict(list)
for s in S: pos[s[0]].append((s[2], s[3]))
if len(sys.argv) > 4:
    for p in json.load(open(sys.argv[4], encoding="utf-8"))["places"]: pos[p[0]].append((p[2], p[3]))
print("== names far from their road")
for n, r in d.items():
    pts = [p for l in r["g"] for p in l[::2] + [l[-1]]]
    for nm, lim in [(r["f"], 6), (r["t"], 6)] + [(v, 4) for v in r["v"]]:
        if nm in pos:
            dm = min(km(a, b) for a in pos[nm] for b in pts)
            if dm > lim: print(" ", n, nm, round(dm, 1), "km")
print("== junctions naming missing roads:", [j["n"] for j in R["junctions"] if any(str(x) not in d for x in j["r"])])
print("== roads with no region:", [n for n in d if not R["roads"].get(n, {}).get("R")])
