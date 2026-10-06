"""Build the offline app (v2, with the OSM basemap) from app_offline_template.html.
Outputs: offline/israeli-road-learner.html (+ bm-1.js, bm-2.js) and transport/*.html for the Word packaging."""
import json, os, shutil
H="/home/claude"; B=H+"/basemap"
t=open(H+"/app_offline_template.html",encoding="utf-8").read()
def rep(old,new,n=1):
    global t
    assert t.count(old)==n,(t.count(old),old[:70]); t=t.replace(old,new)
i=t.index("// offline base map: water background"); j=t.index("drawBase();",i)+len("drawBase();")
t=t[:i]+open(B+"/basemap_renderer.js",encoding="utf-8").read().strip()+t[j:]
rep("function setLabels(on){labelsOn=on;}","function setLabels(on){labelsOn=on;if(typeof bmRedraw===\"function\")bmRedraw();}")
rep("function hideAnswers(on){}","function hideAnswers(on){setLabels(!on);}")
rep("`<b>כביש ${n}</b>: תוואי מלא. לחיצה על הכביש מזיזה את גוגל למקום.`","`<b>כביש ${n}</b>: תוואי מלא.`")
rep(".leaflet-container{font-family:var(--f-body)}",".leaflet-container{font-family:var(--f-body)}\n.bmwarn{margin:0 0 8px;padding:8px 12px;border-radius:8px;background:#fff4d6;border:1px solid #e9ad00;color:#5a4300;font-size:.9rem}")
rep("<script>__LEAFLET_JS__</script>","<script>__LEAFLET_JS__</script>\n<script src=\"bm-1.js\"></script>\n<script src=\"bm-2.js\"></script>")
open(B+"/app_offline_v2_template.html","w",encoding="utf-8").write(t)

lcss=open(B+"/leaflet/leaflet.css",encoding="utf-8").read()
ljs_min=open(B+"/leaflet/leaflet.js",encoding="utf-8").read()
ljs_src=open(B+"/leaflet/leaflet-src.js",encoding="utf-8").read()
roads=open(H+"/roads_min.json",encoding="utf-8").read().strip()
regions=open(H+"/regions.json",encoding="utf-8").read().strip()
os.makedirs(B+"/offline",exist_ok=True); os.makedirs(B+"/transport",exist_ok=True)
clean=t.replace("__LEAFLET_CSS__",lcss).replace("__LEAFLET_JS__",ljs_min).replace("__ROADS__",roads).replace("__REGIONS__",regions)
open(B+"/offline/israeli-road-learner.html","w",encoding="utf-8").write(clean)
for k in (1,2): shutil.copy(B+f"/bm-{k}.js",B+f"/offline/bm-{k}.js")

TH=30000
def compact(o): return json.dumps(o,ensure_ascii=False,separators=(',',':'))
def ser(o):
    c=compact(o)
    if len(c)<=TH: return c
    if isinstance(o,dict): return "{\n"+",\n".join(json.dumps(k,ensure_ascii=False)+":"+ser(v) for k,v in o.items())+"\n}"
    if isinstance(o,list): return "[\n"+",\n".join(ser(e) for e in o)+"\n]"
    return c
tr=t.replace("__LEAFLET_CSS__",lcss).replace("__LEAFLET_JS__",ljs_src).replace("__ROADS__",ser(json.loads(roads))).replace("__REGIONS__",ser(json.loads(regions)))
open(B+"/transport/israeli-road-learner.html","w",encoding="utf-8").write(tr)
for k in (1,2): shutil.copy(B+f"/bm-{k}.js",B+f"/transport/bm-{k}.js")
for f in sorted(os.listdir(B+"/transport")):
    s=open(B+"/transport/"+f,encoding="utf-8").read(); L=s.split("\n")
    print(f"transport/{f}: {len(s):,} chars, {len(L):,} lines, longest {max(map(len,L)):,}")
