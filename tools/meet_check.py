"""Keep, for each junction, only the numbered roads that really meet another of its roads near the junction.

A road passing close by in parallel (e.g. road 77 about 60 m south of Alonim junction, which only crosses 75 at
Yishai interchange) is not a road of that junction. Rule: road A stays if some other listed road B comes within
TOL metres of A inside a disc of RADIUS metres around the junction point (crossing or touching).

Interchanges spread over a kilometre or more, so their exits pick up roads that only pass by (roads 402 and 554
about 600 m east of Ra'anana South interchange, which connects roads 4 and 531). There a road is dropped when it
stays more than 600 m from the interchange centre and does not end within 900 m of it (a road can end at an
interchange through long ramps, like road 67 about 700 m before Ein Tut interchange)."""
import json, math, sys
from shapely.geometry import LineString, Point
RADIUS = {"j": 250}
TOL = {"j": 30}

def prune(roads, regions, verbose=False):
    KX = math.cos(math.radians(31.7)); M = 111320.0
    geo = {}
    def g(n):
        if n not in geo:
            r = roads.get(str(n)); geo[n] = [LineString([(p[1] * KX, p[0]) for p in l]) for l in (r["g"] if r else []) if len(l) > 1]
        return geo[n]
    def termini(n):   # real ends of a road: piece ends with no other piece of the same road within 60 m
        ls = [l for l in (roads.get(str(n)) or {"g": []})["g"] if len(l) > 1]; gs = g(n); out = []
        for i, l in enumerate(ls):
            for e in (l[0], l[-1]):
                pe = Point(e[1] * KX, e[0])
                if all(x.distance(pe) * M > 60 for k, x in enumerate(gs) if k != i): out.append(e)
        return out
    changed = []
    for j in regions["junctions"]:
        if j["k"] == "i" and len(j["r"]) >= 2:
            c = Point(j["p"][1] * KX, j["p"][0])
            def stays(n):
                if min(x.distance(c) for x in g(n)) * M <= 600: return True
                return any(math.hypot((e[0] - j["p"][0]) * M, (e[1] - j["p"][1]) * M * KX) <= 900 for e in termini(n))
            keep = [n for n in j["r"] if g(n) and stays(n)]
            if keep and keep != j["r"]: changed.append((j["n"], j["r"], keep)); j["r"] = keep
            continue
        # only at-grade junctions: at interchanges the roads are joined by ramps and need not cross in the data
        if len(j["r"]) < 2 or j["k"] != "j": continue
        c = Point(j["p"][1] * KX, j["p"][0]); disc = c.buffer(RADIUS[j["k"]] / M); tol = TOL[j["k"]] / M
        near = {n: [x.intersection(disc) for x in g(n)] for n in j["r"]}
        near = {n: [x for x in v if not x.is_empty] for n, v in near.items()}
        keep = [a for a in j["r"] if any(b != a and any(x.distance(y) <= tol for x in near[a] for y in near[b]) for b in j["r"])]
        if keep != j["r"]:
            changed.append((j["n"], j["r"], keep)); j["r"] = keep if keep else j["r"]
    if verbose:
        for n, a, b in changed: print(f"  {n}: {a} -> {b}")
    return changed

if __name__ == "__main__":
    rp, gp = sys.argv[1:3]
    roads = json.load(open(rp, encoding="utf-8")); regions = json.load(open(gp, encoding="utf-8"))
    ch = prune(roads, regions, verbose="-v" in sys.argv)
    print(len(ch), "junctions changed")
    if "--write" in sys.argv:
        json.dump(regions, open(gp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
