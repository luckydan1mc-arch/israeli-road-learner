"""Sea polygon from OSM coastline lines (OSM convention: land on the left, water on the right).

Open coastline lines are extended past the frame and the frame is cut into faces; a face is sea when
more sample points on the water side of the coast fall in it than on the land side (ports and piers
make single samples unreliable)."""
import math
from shapely.geometry import LineString, Polygon, Point, box
from shapely.ops import unary_union, polygonize

def _dir_away(cs, at_start, n=40):
    k = min(len(cs) - 1, n)
    p, q = (cs[k], cs[0]) if at_start else (cs[-1 - k], cs[-1])
    return (q[0] - p[0], q[1] - p[1])

def end_direction(cs, at_start):
    """Where the real coast continues beyond the extract (lon, lat deltas)."""
    x, y = cs[0] if at_start else cs[-1]
    if y < 30.0:                      # Gulf of Eilat/Aqaba: both shores continue south-south-west
        return (-0.35, -1.0)
    if y > 32.5:                      # Rosh Hanikra -> Tyre, Sidon, Beirut: coast runs north-north-east
        return (0.45, 1.0)
    if y < 31.6:                      # Rafah -> El Arish -> Port Said: coast runs almost due west
        return (-1.0, -0.06)
    return _dir_away(cs, at_start)

def build_sea(lines, bbox):
    B = box(*bbox)
    islands = [l for l in lines if l.is_ring]
    open_lines = [l for l in lines if not l.is_ring]
    ext = []
    for l in open_lines:
        cs = list(l.coords)
        out = []
        for at_start in (True, False):
            dx, dy = end_direction(cs, at_start); d = math.hypot(dx, dy) or 1
            x, y = cs[0] if at_start else cs[-1]
            out.append((x + dx / d * 10, y + dy / d * 10))
        ext.append(LineString([out[0]] + cs + [out[1]]).intersection(B))
    faces = list(polygonize(unary_union([B.exterior] + ext)))
    votes = [0] * len(faces)
    for l in open_lines:
        cs = list(l.coords)
        step = max(1, (len(cs) - 1) // 400)
        for i in range(0, len(cs) - 1, step):
            (x0, y0), (x1, y1) = cs[i], cs[i + 1]
            dx, dy = x1 - x0, y1 - y0; d = math.hypot(dx, dy)
            if d == 0: continue
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            for side, v in ((1, 1), (-1, -1)):            # right of the way = water (+1), left = land (-1)
                pt = Point(mx + side * dy / d * 0.0008, my - side * dx / d * 0.0008)
                for fi, f in enumerate(faces):
                    if f.contains(pt): votes[fi] += v; break
    sea = unary_union([f for f, v in zip(faces, votes) if v > 0])
    for isl in islands:
        sea = sea.difference(Polygon(isl.coords))
    return sea, votes
