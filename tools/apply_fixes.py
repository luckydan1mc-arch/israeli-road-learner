"""Apply tools/fixes.json (bad road refs, misplaced junctions) to the build data.

Usage:
  python3 apply_fixes.py roads_min.json regions.json      # during a build (edits in place)
  python3 apply_fixes.py --html ../index.html ...          # patch already-built app files
"""
import json, os, re, sys

FIX = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixes.json"), encoding="utf-8"))
DROP = set(FIX.get("drop_roads", {}))


def fix_roads(roads):
    for k in DROP:
        roads.pop(k, None)
    return roads


def fix_regions(rg):
    if isinstance(rg.get("roads"), dict):
        for k in DROP:
            rg["roads"].pop(k, None)
    for j in rg.get("junctions", []):
        j["r"] = [n for n in j["r"] if str(n) not in DROP]
        f = FIX.get("junctions", {}).get(j["n"])
        if f:
            for key in ("p", "r", "k"):
                if key in f:
                    j[key] = f[key]
    # one name per place: drop stray labels, fold spelling variants into the kept name
    drop, drop_near = set(), []      # whole name, or one place: {"name":..., "near":[lat, lon]}
    for k, v in FIX.get("drop_junctions", {}).items():
        if isinstance(v, dict) and "near" in v: drop_near.append((v["name"], v["near"]))
        else: drop.add(k)
    def dropped(j):
        return j["n"] in drop or any(j["n"] == n and abs(j["p"][0] - p[0]) < .01 and abs(j["p"][1] - p[1]) < .01 for n, p in drop_near)
    ren = {k: v[0] for k, v in FIX.get("rename_junctions", {}).items()}
    js = [j for j in rg.get("junctions", []) if not dropped(j)]
    keep = {j["n"]: j for j in js if j["n"] not in ren}
    out = []
    for j in js:
        if j["n"] in ren:
            t = keep.get(ren[j["n"]])
            if t is not None:          # merge into the junction that already has the kept name
                t["r"] = t["r"] + [n for n in j["r"] if n not in t["r"]]
                continue
            j["n"] = ren[j["n"]]
            if j["n"].startswith("מחלף"): j["k"] = "i"
        out.append(j)
    rg["junctions"] = [j for j in out if j["r"]]
    return rg


def dump(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def patch_html(path):
    s = open(path, encoding="utf-8").read()
    for sid, fn in (("roads", fix_roads), ("regions", fix_regions)):
        m = re.search(r'(<script id="%s" type="application/json">)(.*?)(</script>)' % sid, s, re.S)
        if not m:
            raise SystemExit(f"{path}: no {sid} block")
        data = fn(json.loads(m.group(2).replace("<\\/", "</")))
        s = s[:m.start(2)] + dump(data).replace("</", "<\\/") + s[m.end(2):]
    open(path, "w", encoding="utf-8").write(s)
    print("patched", path)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--html":
        for p in a[1:]:
            patch_html(p)
    else:
        rp, gp = a
        json.dump(fix_roads(json.load(open(rp, encoding="utf-8"))), open(rp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        json.dump(fix_regions(json.load(open(gp, encoding="utf-8"))), open(gp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        print("fixes applied")
