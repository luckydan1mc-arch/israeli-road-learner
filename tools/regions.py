"""Assign every road to regions (groups of regional councils) and to regional councils.
Writes regions.json: {regions:[{id,name,councils:[cid..],outline:[[[lat,lon]..]..]}], councils:[{id,name,region}], roads:{ref:{R:[..],C:[..]}}}
"""
import json, math, sys, collections, os
import osmium
from shapely.geometry import Polygon, MultiPolygon, Point, LineString
from shapely.ops import unary_union
from shapely.strtree import STRtree
from shapely.prepared import prep

PBF = sys.argv[1]
ROADS = json.load(open("roads2.json"))

REGIONS = [
 ("golan", "רמת הגולן", ["גולן"]),
 ("upper_galilee", "הגליל העליון והחולה", ["גליל עליון", "מבואות החרמון", "מרום הגליל"]),
 ("west_galilee", "הגליל המערבי", ["מטה אשר", "מעלה יוסף", "משגב"]),
 ("lower_galilee", "הגליל התחתון והכנרת", ["גליל תחתון", "עמק הירדן", "אל בטוף"]),
 ("valleys", "העמקים: יזרעאל, בית שאן והגלבוע", ["עמק יזרעאל", "גלבוע", "עמק המעיינות", "מגידו", "בוסתן-אל-מרג'"]),
 ("haifa", "חיפה, הקריות והכרמל", ["זבולון", "חוף הכרמל"]),
 ("menashe", "מנשה ונחל עירון", ["מנשה", "אלונה"]),
 ("sharon", "השרון", ["עמק חפר", "חוף השרון", "לב השרון", "דרום השרון"]),
 ("dan", "גוש דן והמרכז", ["שדות דן", "חבל מודיעין", "גזר"]),
 ("shfela", "השפלה", ["גן רווה", "חבל יבנה", "ברנר", "גדרות", "באר טוביה", "נחל שורק", "יואב"]),
 ("jerusalem", "ירושלים והרי יהודה", ["מטה יהודה"]),
 ("samaria", "השומרון", ["שומרון"]),
 ("binyamin", "בנימין", ["מטה בנימין"]),
 ("judea", "גוש עציון והר חברון", ["גוש עציון", "הר חברון"]),
 ("jordan_deadsea", "בקעת הירדן וצפון ים המלח", ["ערבות הירדן", "מגילות ים המלח"]),
 ("lachish", "לכיש וחבל שפיר", ["לכיש", "שפיר"]),
 ("west_negev", "הנגב המערבי וחוף אשקלון", ["חוף אשקלון", "שער הנגב", "אשכול", "שדות נגב", "מרחבים"]),
 ("north_negev", "באר שבע והנגב הצפוני", ["בני שמעון", "נווה מדבר", "אל-קסום"]),
 ("negev_highlands", "הר הנגב", ["רמת נגב"]),
 ("arava", "ים המלח הדרומי, הערבה ואילת", ["תמר", "הערבה התיכונה", "חבל אילות"]),
]
# cities inside these sub-districts go to a fixed region (otherwise: nearest regional council's region)
NAFA_OVERRIDE = {"נפת השרון": "sharon", "נפת רמת הגולן": "golan", "נפת תל אביב": "dan", "נפת ירושלים": "jerusalem", "נפת פתח תקווה": "dan"}
NAME_OVERRIDE = {"מעלה אדומים": "binyamin", "כפר סבא": "sharon", "רעננה": "sharon", "הוד השרון": "sharon"}   # surrounded by Mateh Binyamin
COUNTRY_IDS = (1473946, 1613659, 1803010, 16119376)

def poly_of(a):
    ps = []
    for outer in a.outer_rings():
        ps.append(Polygon([(n.lon, n.lat) for n in outer], [[(n.lon, n.lat) for n in r] for r in a.inner_rings(outer)]))
    return MultiPolygon(ps).buffer(0)

class A(osmium.SimpleHandler):
    def __init__(s):
        super().__init__(); s.munis = []; s.nafot = []; s.country = []; s.wb = []
    def area(s, a):
        if a.from_way(): return
        t = a.tags
        if a.orig_id() in COUNTRY_IDS:
            pg = poly_of(a); s.country.append(pg)
            if a.orig_id() in (1613659, 1803010): s.wb.append(pg)
            return
        if t.get("boundary") != "administrative": return
        lv = t.get("admin_level"); nm = t.get("name:he") or t.get("name") or ""
        if lv == "5": s.nafot.append((nm, poly_of(a)))
        elif lv == "8": s.munis.append((nm, poly_of(a)))

H = A(); H.apply_file(PBF, locations=True, idx="flex_mem")
country = unary_union(H.country)
cprep = prep(country.buffer(0.002))
print("munis", len(H.munis), "nafot", len(H.nafot))

rc_name_to_region = {}
for rid, _, names in REGIONS:
    for n in names: rc_name_to_region[n] = rid
councils = []  # (cid, short name, region, polygon)
others = []    # (name, polygon) municipalities that are not regional councils
for nm, pg in H.munis:
    c = pg.centroid
    if not cprep.contains(c): continue
    if nm.startswith("מועצה אזורית"):
        short = nm.replace("מועצה אזורית", "").strip()
        rid = rc_name_to_region.get(short)
        if rid is None:
            print("UNMAPPED council", short); continue
        councils.append((len(councils), short, rid, pg))
    else:
        others.append((nm, pg))
print("councils", len(councils), "others", len(others))
missing = set(rc_name_to_region) - set(c[1] for c in councils)
print("missing councils:", missing)

nafa_prep = [(n, prep(p)) for n, p in H.nafot]
# beyond the Green Line only the Judea & Samaria regions apply, and vice versa
WB_REGIONS = {"samaria", "binyamin", "judea", "jordan_deadsea"}
wb_poly = unary_union(H.wb); wbp = prep(wb_poly)
def in_wb(pt): return wbp.contains(pt)
BOTH_SIDES = {"jerusalem"}   # Jerusalem municipality spans the Green Line
def side_ok(rid, want_wb): return rid in BOTH_SIDES or (rid in WB_REGIONS) == want_wb
rc_tree = STRtree([c[3] for c in councils])
def nearest_council_region(pt):
    want_wb = in_wb(pt)
    best = None
    for c in councils:
        if not side_ok(c[2], want_wb): continue
        d = c[3].distance(pt)
        if best is None or d < best[0]: best = (d, c[2])
    return best[1]
units = []  # (region, councilId or None, polygon)
# a council that straddles two familiar regions is split along a latitude line (council filter still covers all of it)
SPLITS = {"דרום השרון": (32.10, "dan")}   # Nahshonim / Givat HaShlosha / Mazor area belongs with the center
from shapely.geometry import box as _sbox
for c in councils:
    if c[1] in SPLITS:
        lat, south_rid = SPLITS[c[1]]
        north = c[3].intersection(_sbox(30, lat, 40, 40)); south = c[3].intersection(_sbox(30, 20, 40, lat))
        if not north.is_empty: units.append((c[2], c[0], north))
        if not south.is_empty: units.append((south_rid, c[0], south))
    else:
        units.append((c[2], c[0], c[3]))
for nm, pg in others:
    ce = pg.representative_point(); rid = NAME_OVERRIDE.get(nm)
    for n, pp in nafa_prep:
        if rid is None and pp.contains(ce) and n in NAFA_OVERRIDE: rid = NAFA_OVERRIDE[n]; break
    if rid is None:
        rid = nearest_council_region(ce)
    units.append((rid, None, pg))
# ================= exact, gap-free region map =================
from shapely.ops import linemerge
from shapely.geometry import box as _box
def parts(g):
    if g.is_empty: return []
    if g.geom_type == "Polygon": return [g]
    return [p for p in getattr(g, "geoms", []) if p.geom_type == "Polygon" and not p.is_empty]

# land = the country minus the Mediterranean, cut along the real coastline
class Coast(osmium.SimpleHandler):
    def __init__(s): super().__init__(); s.lines = []
    def way(s, w):
        if w.tags.get("natural") == "coastline":
            try: pts = [(n.lon, n.lat) for n in w.nodes]
            except osmium.InvalidLocationError: return
            if len(pts) > 1 and all(31.0 < y < 33.2 and x < 35.3 for x, y in pts): s.lines.append(LineString(pts))
CO = Coast(); CO.apply_file(PBF, locations=True, idx="flex_mem")
merged = linemerge(CO.lines)
coast = max(merged.geoms, key=lambda g: g.length) if merged.geom_type == "MultiLineString" else merged
cc = list(coast.coords)
if cc[0][1] < cc[-1][1]: cc = cc[::-1]
sea = Polygon(cc + [(cc[-1][0] - 2, cc[-1][1]), (cc[0][0] - 2, cc[0][1])]).buffer(0)
sea = sea.union(_box(33.5, 33.095, 35.095, 33.7))   # waters north-west of Rosh Hanikra (beyond the coastline extract)
land = country.buffer(0).difference(sea)
wb_land = land.intersection(wb_poly); il_land = land.difference(wb_poly)
print("coast pts", len(cc))

reg_ids = [r[0] for r in REGIONS]
# 1) pieces: every municipality cut on the Green Line; a piece keeps its region only if that region is allowed on its side
pieces = []   # [polygon, region or None, is_wb]
for rid, cid, pg in units:
    for side_geom, is_wb in ((wb_land, True), (il_land, False)):
        for p in parts(pg.intersection(side_geom)):
            if p.area < 1e-7: continue
            pieces.append([p, rid if side_ok(rid, is_wb) else None, is_wb])
# overlapping municipal polygons in the source data: earlier pieces win, later ones are trimmed so nothing overlaps
for k in range(len(pieces)):
    g = pieces[k][0]
    prev = [pieces[j][0] for j in range(k) if pieces[j][0].bounds[0] <= g.bounds[2] and pieces[j][0].bounds[2] >= g.bounds[0]
            and pieces[j][0].bounds[1] <= g.bounds[3] and pieces[j][0].bounds[3] >= g.bounds[1] and pieces[j][0].intersects(g)]
    if prev: pieces[k][0] = g.difference(unary_union(prev))
pieces = [p for p in pieces if not p[0].is_empty and p[0].area > 1e-8]
_exp = []
for p in pieces:
    for q in parts(p[0]): _exp.append([q, p[1], p[2]])
pieces = _exp
covered = unary_union([p[0] for p in pieces])
for side_geom, is_wb in ((wb_land, True), (il_land, False)):
    for p in parts(side_geom.difference(covered)):
        if p.area < 1e-8: continue
        pieces.append([p, None, is_wb])
print("pieces", len(pieces), "unassigned", sum(1 for p in pieces if p[1] is None))

def shared_len(a, b):
    try: return a.boundary.intersection(b.buffer(1e-5)).length
    except Exception: return 0.0
ptree = STRtree([p[0] for p in pieces])
def neighbour_votes(k):
    g = pieces[k][0]; votes = collections.Counter()
    for j in ptree.query(g.buffer(1e-5)):
        if j == k or pieces[j][1] is None: continue
        if not side_ok(pieces[j][1], pieces[k][2]): continue
        L = shared_len(g, pieces[j][0])
        if L > 0: votes[pieces[j][1]] += L
    return votes
# 2) open land between municipalities: split along the midline between the nearest municipalities (Voronoi of their borders)
from shapely.ops import voronoi_diagram
from shapely.geometry import MultiPoint
def sample_boundary(g, step=0.003):
    pts = []
    for p in parts(g):
        for ring in [p.exterior] + list(p.interiors):
            L = ring.length; n = max(4, int(L / step))
            for k in range(n): pts.append(ring.interpolate(k * L / n))
    return pts
for side_geom, is_wb in ((wb_land, True), (il_land, False)):
    gap_idx = [k for k, p in enumerate(pieces) if p[1] is None and p[2] == is_wb]
    if not gap_idx: continue
    gap_union = unary_union([pieces[k][0] for k in gap_idx])
    near = gap_union.buffer(0.05)
    seeds = []; labels = []
    for p in pieces:
        if p[1] is None or p[2] != is_wb or not p[0].intersects(near): continue
        for q in sample_boundary(p[0].intersection(near.buffer(0.02))):
            seeds.append(q); labels.append(p[1])
    print("side wb" if is_wb else "side il", "gap pieces", len(gap_idx), "seeds", len(seeds))
    vd = voronoi_diagram(MultiPoint(seeds), envelope=near.envelope.buffer(0.1))
    seed_tree = STRtree(seeds)
    by_lab = collections.defaultdict(list)
    for cell in vd.geoms:
        cands = seed_tree.query(cell)
        inside = [i for i in cands if cell.contains(seeds[i])] or list(cands)
        if not inside: continue
        by_lab[labels[inside[0]]].append(cell)
    newp = []
    for lab, cells in by_lab.items():
        area = unary_union(cells).intersection(gap_union)
        for q in parts(area):
            if q.area > 1e-8: newp.append([q, lab, is_wb])
    for k in sorted(gap_idx, reverse=True): pieces.pop(k)
    pieces.extend(newp)
ptree = STRtree([p[0] for p in pieces])
for _ in range(30):
    changed = 0
    for k, p in enumerate(pieces):
        if p[1] is not None: continue
        v = neighbour_votes(k)
        if v: p[1] = v.most_common(1)[0][0]; changed += 1
    if not changed: break
for k, p in enumerate(pieces):          # anything still isolated: nearest allowed region by distance
    if p[1] is None:
        best = None
        for j, q in enumerate(pieces):
            if q[1] is None or not side_ok(q[1], p[2]): continue
            d = q[0].distance(p[0])
            if best is None or d < best[0]: best = (d, q[1])
        p[1] = best[1]
# 3) islands: a detached piece mostly surrounded by another region joins that region
def region_union():
    return {rid: unary_union([p[0] for p in pieces if p[1] == rid]) for rid in reg_ids}
for it in range(3):
    RU = region_union(); moved = 0
    for k, p in enumerate(pieces):
        own = [q for q in parts(RU[p[1]]) if q.intersects(p[0].representative_point().buffer(1e-6))]
        comp = own[0] if own else p[0]
        total_area = sum(q.area for q in parts(RU[p[1]]))
        if comp.area >= 0.25 * max(q.area for q in parts(RU[p[1]])): continue   # part of the region's main body
        v = neighbour_votes(k); v.pop(p[1], None)
        if not v: continue
        perim = comp.boundary.length
        cand, L = v.most_common(1)[0]
        if L >= 0.4 * p[0].boundary.length:
            p[1] = cand; moved += 1
    print("island pass", it, "moved", moved)
    if not moved: break
RU = region_union()
reg_poly = {rid: RU[rid].buffer(0) for rid in reg_ids}

# road assignment uses exactly these region shapes
KX = math.cos(math.radians(31.7))
def seg_len_km(a, b): return math.hypot((a[0] - b[0]) * 110.6, (a[1] - b[1]) * 110.6 * KX)
reg_prep = [(rid, prep(reg_poly[rid])) for rid in reg_ids]
reg_tree = STRtree([reg_poly[r] for r in reg_ids])
utree = STRtree([u[2] for u in units])
def council_at(pt):
    for i in utree.query(pt):
        if units[i][1] is not None and units[i][2].contains(pt): return units[i][1]
    return None
def region_at(lat, lon):
    pt = Point(lon, lat)
    for i in reg_tree.query(pt):
        if reg_prep[i][1].contains(pt): return reg_ids[i]
    return reg_ids[reg_tree.nearest(pt)]      # on the coastline / just outside: nearest region

out_roads = {}
for ref, r in ROADS.items():
    rl = collections.Counter(); cl = collections.Counter(); total = 0
    for line in r["g"]:
        for a, b in zip(line, line[1:]):
            L = seg_len_km(a, b); k = max(1, int(L / 0.3))
            for j in range(k):
                t = (j + 0.5) / k
                lat = a[0] + (b[0] - a[0]) * t; lon = a[1] + (b[1] - a[1]) * t
                rg = region_at(lat, lon); cid = council_at(Point(lon, lat))
                rl[rg] += L / k; total += L / k
                if cid is not None: cl[cid] += L / k
    if total == 0: continue
    R = [g for g, l in rl.items() if l / total >= 0.3 or l >= 8]
    if not R: R = [rl.most_common(1)[0][0]]
    C = [c for c, l in cl.items() if l >= 0.8 or l / total >= 0.25]
    out_roads[ref] = {"R": sorted(reg_ids.index(g) for g in R), "C": sorted(C)}

def rings(geom, tol=0.0004):
    g = geom.simplify(tol, preserve_topology=True)
    res = []
    for p in parts(g):
        if p.area < 2e-6: continue
        res.append([[round(y, 5), round(x, 5)] for x, y in p.exterior.coords])
        for h in p.interiors:
            if Polygon(h).area >= 2e-6: res.append([[round(y, 5), round(x, 5)] for x, y in h.coords])
    return res
# junctions / interchanges: region and council of each point
JN = json.load(open("junctions.json")) if os.path.exists("junctions.json") else []
junc_out = []
for j in JN:
    la, lo = j["p"]; cid = council_at(Point(lo, la))
    junc_out.append({**j, "R": [reg_ids.index(region_at(la, lo))], "C": [cid] if cid is not None else []})
regions_out = [{"id": rid, "name": name, "councils": [c[0] for c in councils if c[2] == rid], "o": rings(reg_poly[rid])} for rid, name, _ in REGIONS]
councils_out = [{"id": c[0], "name": c[1], "region": reg_ids.index(c[2]), "o": rings(c[3].intersection(land), 0.0006)} for c in councils]
json.dump({"regions": regions_out, "councils": councils_out, "roads": out_roads, "junctions": junc_out}, open("regions.json", "w"), ensure_ascii=False, separators=(",", ":"))

# report
tot = sum(reg_poly[r].area for r in reg_ids); ov = 0
for a in range(len(reg_ids)):
    for b in range(a + 1, len(reg_ids)):
        ov += reg_poly[reg_ids[a]].intersection(reg_poly[reg_ids[b]]).area
print("land area", round(land.area, 4), "regions area", round(tot, 4), "overlap", round(ov, 6), "gap", round(land.difference(unary_union(list(reg_poly.values()))).area, 6))
by_reg = collections.Counter(); by_reg3 = collections.Counter()
for ref, x in out_roads.items():
    for g in x["R"]:
        by_reg[g] += 1
        if len(ref) == 3: by_reg3[g] += 1
for i, (rid, name, _) in enumerate(REGIONS):
    print(f"{name}: {by_reg[i]} roads, 3-digit {by_reg3[i]}, parts {len(parts(reg_poly[rid]))}")
for ref in ["55", "576", "654", "38", "1", "90", "6", "2", "4"]:
    print(ref, [REGIONS[g][1] for g in out_roads[ref]["R"]])
import os; print("size", os.path.getsize("regions.json"))
