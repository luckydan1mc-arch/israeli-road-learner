"""Encode basemap.json into plain-text JS data files the app loads with <script src>.

Encoding is Word-safe: only A-Z a-z 0-9 - _ inside the geometry strings.
Each value is a zig-zag integer in base 32, with the first 32 letters ending a number and the last 32
continuing it. Coordinates are 1e-5 degree integers; inside a feature every point is a delta from the
previous one; each feature's first point is a delta from the previous feature's first point.
Features are separated by ',' and polygon rings by ';'. Every chunk starts from (0,0), so chunks can be
decoded independently and in any order.
"""
import json, sys, collections

ALPH = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
SRC, OUTPREFIX = sys.argv[1], sys.argv[2]
MAXFILE = int(sys.argv[3]) if len(sys.argv) > 3 else 2_600_000
LINE = 2000          # characters per text line
CHUNK = 120_000      # characters per independent chunk

def enc(v):
    z = 2 * v if v >= 0 else -2 * v - 1
    out = []
    while z >= 32:
        out.append(ALPH[32 + (z & 31)]); z >>= 5
    out.append(ALPH[z])
    return "".join(out)

def morton(la, lo):
    x = int((lo - 33.0) * 100); y = int((la - 29.0) * 100)
    m = 0
    for b in range(10):
        m |= ((x >> b) & 1) << (2 * b) | ((y >> b) & 1) << (2 * b + 1)
    return m

def q(p): return (round(p[0] * 1e5), round(p[1] * 1e5))

def encode_features(feats, polygon):
    """feats: list of lines (list of [lat,lon]) or polygons (list of rings). Returns list of chunks (strings)."""
    first = (lambda f: f[0][0]) if polygon else (lambda f: f[0])
    feats = sorted(feats, key=lambda f: morton(*first(f)))
    chunks, cur, size, anchor = [], [], 0, (0, 0)
    for f in feats:
        rings = f if polygon else [f]
        parts = []
        for r in rings:
            pts = [q(p) for p in r]
            s = [enc(pts[0][0] - anchor[0]), enc(pts[0][1] - anchor[1])]
            anchor = pts[0]
            for a, b in zip(pts, pts[1:]):
                s.append(enc(b[0] - a[0])); s.append(enc(b[1] - a[1]))
            parts.append("".join(s))
        txt = ";".join(parts)
        cur.append(txt); size += len(txt) + 1
        if size >= CHUNK:
            chunks.append(",".join(cur)); cur, size, anchor = [], 0, (0, 0)
    if cur: chunks.append(",".join(cur))
    return chunks

bm = json.load(open(SRC))
records = []     # (key, chunk)
for c, lines in sorted(bm["roads"].items(), key=lambda kv: int(kv[0])):
    for ch in encode_features(lines, False): records.append(("r" + str(c), ch))
for k in ("sea", "water", "built", "green"):
    for ch in encode_features(bm[k], True): records.append((k, ch))
for ch in encode_features(bm["border"], False): records.append(("border", ch))

def js_record(k, ch):
    lines = [ch[i:i + LINE] for i in range(0, len(ch), LINE)]
    return '(window.IRL_BASE=window.IRL_BASE||[]).push({k:"%s",d:[\n%s\n]});\n' % (k, ",\n".join('"' + l + '"' for l in lines))

places = "(window.IRL_BASE=window.IRL_BASE||[]).push({k:\"places\",d:[\n" + ",\n".join(
    json.dumps(p, ensure_ascii=False, separators=(",", ":")) for p in bm["places"]) + "\n]});\n"
wl = "(window.IRL_BASE=window.IRL_BASE||[]).push({k:\"wlabels\",d:[\n" + ",\n".join(
    json.dumps(p, ensure_ascii=False, separators=(",", ":")) for p in bm["wlabels"]) + "\n]});\n"

# street-name anchors: a name dictionary + 5 integers per anchor (name index, dlat, dlon, angle+90, class)
streets = json.load(open(sys.argv[4])) if len(sys.argv) > 4 else []
snames_blob = sanch_blobs = ""
if streets:
    freq = collections.Counter(a[0] for a in streets)
    names = [n for n, _ in freq.most_common()]
    idx = {n: i for i, n in enumerate(names)}
    rows = [names[i:i + 40] for i in range(0, len(names), 40)]
    snames_blob = "(window.IRL_BASE=window.IRL_BASE||[]).push({k:\"snames\",d:[\n" + ",\n".join(
        ",".join(json.dumps(n, ensure_ascii=False) for n in r) for r in rows) + "\n]});\n"
    anc = sorted(streets, key=lambda a: morton(a[1], a[2]))
    for s0 in range(0, len(anc), 6000):
        prev = (0, 0); out = []
        for a in anc[s0:s0 + 6000]:
            la, lo = round(a[1] * 1e5), round(a[2] * 1e5)
            out.append(enc(idx[a[0]]) + enc(la - prev[0]) + enc(lo - prev[1]) + enc(int(a[3]) + 90) + enc(a[4]))
            prev = (la, lo)
        records.append(("sanch", "".join(out)))

# pack: small/important layers first so file 1 alone already gives a usable map
order = ["sea", "water", "border", "r0", "r1", "r2", "r3"]
recs = sorted(records, key=lambda r: (order.index(r[0]) if r[0] in order else len(order), ))
blobs = [places, wl] + ([snames_blob] if snames_blob else []) + [js_record(k, ch) for k, ch in recs]
files, cur = [], ""
for b in blobs:
    if cur and len(cur) + len(b) > MAXFILE:
        files.append(cur); cur = ""
    cur += b
if cur: files.append(cur)
n = len(files)
for i, f in enumerate(files, 1):
    hdr = "/* Israeli Road Learner - offline basemap, part %d of %d (OpenStreetMap data, ODbL) */\n" % (i, n)
    open("%s-%d.js" % (OUTPREFIX, i), "w", encoding="utf-8").write(hdr + f + "(window.IRL_BASE_FILES=window.IRL_BASE_FILES||[]).push(%d);\n" % i)
    print("file", i, "chars", len(f), "lines", f.count("\n"))
print("files", n, "total chars", sum(len(f) for f in files))
