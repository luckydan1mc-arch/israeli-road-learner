"""Remove stray pieces of a road: OSM ways tagged with a road number far away from the road itself.

usage: prune_fragments.py roads_min.json regions.json        (edits both in place)

A road's lines are grouped into pieces (lines within 3 km of each other belong together). A piece shorter
than 2 km that lies more than 3 km from the road's longest piece is a tagging error (e.g. 0.7 km of "3527"
34 km away from road 3527) and is dropped. The regions and councils of a changed road are recomputed
from its remaining lines.
"""
import json, math, sys
from functools import reduce
from shapely.geometry import LineString, Polygon

ROADS, REGIONS = sys.argv[1:3]
MAX_LEN, MIN_GAP, JOIN = 2.0, 3.0, 3.0   # km

roads = json.load(open(ROADS, encoding="utf-8"))
rg = json.load(open(REGIONS, encoding="utf-8"))


def km(a, b): return math.hypot((a[0] - b[0]) * 110, (a[1] - b[1]) * 94)
def length(l): return sum(km(l[i], l[i + 1]) for i in range(len(l) - 1))


def area(rings):   # flat list of rings filled even-odd, as drawn on the map
    ps = [Polygon([(x, y) for y, x in r]).buffer(0) for r in rings if len(r) >= 4]
    return reduce(lambda a, b: a.symmetric_difference(b), ps) if ps else Polygon()


reg = [area(r["o"]) for r in rg["regions"]]
cou = [area(c["o"]) for c in rg["councils"]]

changed = []
for n, r in roads.items():
    lines = r["g"]; N = len(lines); par = list(range(N))
    def f(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    S = [l[::max(1, len(l) // 20)] + [l[-1]] for l in lines]
    for i in range(N):
        for j in range(i + 1, N):
            if f(i) != f(j) and any(km(a, b) < JOIN for a in S[i] for b in S[j]): par[f(i)] = f(j)
    pieces = {}
    for i in range(N): pieces.setdefault(f(i), []).append(i)
    if len(pieces) < 2: continue
    ps = sorted(pieces.values(), key=lambda c: -sum(length(lines[i]) for i in c))
    main, drop = ps[0], []
    for c in ps[1:]:
        ln = sum(length(lines[i]) for i in c)
        gap = min(km(a, b) for i in c for j in main for a in S[i] for b in S[j])
        if ln < MAX_LEN and gap > MIN_GAP: drop += c
    if not drop: continue
    keep = [l for i, l in enumerate(lines) if i not in drop]
    r["g"] = keep
    geo = [LineString([(x, y) for y, x in l]) for l in keep if len(l) >= 2]
    if n in rg["roads"]:
        rg["roads"][n]["R"] = [i for i, p in enumerate(reg) if any(g.intersects(p) for g in geo)]
        rg["roads"][n]["C"] = [i for i, p in enumerate(cou) if any(g.intersects(p) for g in geo)]
    changed.append(f"{n} (-{round(sum(length(lines[i]) for i in drop), 1)} km)")

json.dump(roads, open(ROADS, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
json.dump(rg, open(REGIONS, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("stray pieces removed:", ", ".join(changed) or "none")
