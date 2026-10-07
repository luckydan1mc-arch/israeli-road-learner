#!/usr/bin/env bash
# Rebuild index.html from a fresh OpenStreetMap extract of Israel.
# Usage: tools/build.sh path/to/israel-and-palestine-latest.osm.pbf
# Requires: pip install osmium shapely numpy
set -euo pipefail
PBF="$1"; cd "$(dirname "$0")"
python3 extract_roads.py "$PBF" roads.json
python3 enrich.py "$PBF" roads.json roads2.json
python3 - <<'PY'
import json
d = json.load(open("roads2.json")); out = {}
for k, r in d.items():
    out[k] = {"g": r["g"], "f": r["from"], "t": r["to"], "v": r["via"][:6], "d": r["dir"], "ok": int(r["dir"] == r["geo"]), "h": r["hw"], "r": r["reg"], "s": r["span"]}
open("roads_min.json", "w").write(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
PY
python3 junctions.py "$PBF" roads2.json junctions.json
python3 regions.py "$PBF"
python3 apply_fixes.py roads_min.json regions.json
python3 render_online.py roads_min.json regions.json ../index.html
