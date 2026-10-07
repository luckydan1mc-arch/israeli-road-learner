"""Build the offline version from the same app_template.html as the website.
Usage: build_offline.py roads_min.json regions.json leaflet_dist_dir basemap_dir out_dir
Writes out_dir/offline/ (ready to run: html + bm-1.js + bm-2.js) and out_dir/transport/ (same app with short lines,
for carrying the files inside Word documents)."""
import base64, json, os, re, shutil, sys
here = os.path.dirname(os.path.abspath(__file__)); tools = os.path.dirname(here)
roads_p, regions_p, ldist, bmdir, outdir = sys.argv[1:6]
t = open(os.path.join(tools, "app_template.html"), encoding="utf-8").read()

def block(name, new, js=False):
    global t
    a, b = (f"/*{name}*/", f"/*/{name}*/") if js else (f"<!--{name}-->", f"<!--/{name}-->")
    i = t.index(a); j = t.index(b, i) + len(b); t = t[:i] + new + t[j:]

block("WEBAPP", '<link rel="icon" href="__EMBLEM__">')
block("ONLINE-HEAD", "<style>__LEAFLET_CSS__</style>")
block("ONLINE-BASESEG", "")
block("GOOGLE-PANEL", "")
block("NOTE", '<p class="note">מקור התוואי והמפה: OpenStreetMap (גרסה מ־2.10.2026). גרסה לא־מקוונת: הכול מצויר במחשב, בלי חיבור לאינטרנט. ההתקדמות נשמרת בדפדפן הזה. הסמל: ענף מבצעים.</p>')
block("ONLINE-SCRIPTS", '<script>__LEAFLET_JS__</script>\n<script src="bm-1.js"></script>\n<script src="bm-2.js"></script>')
block("ONLINE-MAP", '''/* ---------- map (offline: drawn locally from OpenStreetMap data, no internet) ---------- */
const ONLINE=false;
const canvas=L.canvas({tolerance:matchMedia("(pointer:coarse)").matches?16:8});
const map=L.map("map",{preferCanvas:true,renderer:canvas,zoomSnap:.5,attributionControl:false}).setView([31.6,35.0],8);
let labelsOn=true,baseKey="map";
function applyLabels(){}
function setLabels(on){labelsOn=on;if(typeof bmRedraw==="function")bmRedraw();}
function setBase(){}
''' + open(os.path.join(here, "basemap_renderer.js"), encoding="utf-8").read(), js=True)
block("GOOGLE-JS", "function setGoogle(){}\nfunction hideGoogle(){}", js=True)

emb = "data:image/png;base64," + base64.b64encode(open(os.path.join(tools, "emblem.png"), "rb").read()).decode()
lcss = open(os.path.join(ldist, "leaflet.css"), encoding="utf-8").read()
roads = open(roads_p, encoding="utf-8").read().strip(); regions = open(regions_p, encoding="utf-8").read().strip()

def compact(o): return json.dumps(o, ensure_ascii=False, separators=(",", ":"))
def ser(o, th=30000):   # same JSON, but no line longer than ~30k characters (Word copes with that on a slow PC)
    c = compact(o)
    if len(c) <= th: return c
    if isinstance(o, dict): return "{\n" + ",\n".join(json.dumps(k, ensure_ascii=False) + ":" + ser(v) for k, v in o.items()) + "\n}"
    if isinstance(o, list): return "[\n" + ",\n".join(ser(e) for e in o) + "\n]"
    return c

for kind, ljs, rd, rg in (("offline", "leaflet.js", roads, regions),
                         ("transport", "leaflet-src.js", ser(json.loads(roads)), ser(json.loads(regions)))):
    d = os.path.join(outdir, kind); os.makedirs(d, exist_ok=True)
    js = open(os.path.join(ldist, ljs), encoding="utf-8").read()
    for x in (js, lcss): assert "</script>" not in x and "</style>" not in x
    html = t.replace("__LEAFLET_CSS__", lcss).replace("__LEAFLET_JS__", js).replace("__ROADS__", rd).replace("__REGIONS__", rg)
    if kind == "transport":   # Word chokes on one very long line: the emblem is set from short string chunks instead
        html = html.replace('src="__EMBLEM__"', 'id="emblemImg" alt=""').replace('<link rel="icon" href="__EMBLEM__">', "")
        chunks = [emb[i:i + 1500] for i in range(0, len(emb), 1500)]
        html = html.replace("</body>", "<script>\n(function(){var s=[\n" + ",\n".join('"' + c + '"' for c in chunks) +
                            "\n].join('');var i=document.getElementById('emblemImg');if(i)i.src=s;var l=document.createElement('link');l.rel='icon';l.href=s;document.head.appendChild(l);})();\n</script>\n</body>")
    else:
        html = html.replace("__EMBLEM__", emb)
    open(os.path.join(d, "israeli-road-learner.html"), "w", encoding="utf-8").write(html)
    for k in (1, 2): shutil.copy(os.path.join(bmdir, f"bm-{k}.js"), os.path.join(d, f"bm-{k}.js"))
    L = html.split("\n"); print(kind, f"{len(html):,} chars, {len(L):,} lines, longest {max(map(len, L)):,}")
