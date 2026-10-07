"""Assemble index.html (online version) from app_template.html, the data files and the emblem."""
import base64, sys, os
here = os.path.dirname(os.path.abspath(__file__))
roads, regions, out = sys.argv[1], sys.argv[2], sys.argv[3]
t = open(os.path.join(here, "app_template.html"), encoding="utf-8").read()
emb = "data:image/png;base64," + base64.b64encode(open(os.path.join(here, "emblem.png"), "rb").read()).decode()
d = open(roads, encoding="utf-8").read().replace("</", "<\\/"); g = open(regions, encoding="utf-8").read().replace("</", "<\\/")
open(out, "w", encoding="utf-8").write(t.replace("__EMBLEM__", emb).replace("__ROADS__", d).replace("__REGIONS__", g))
print(out, "written")
