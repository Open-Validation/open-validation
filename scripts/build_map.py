"""Stage C: build the map file docs/map/uk-lpa.geojson from the boundary download.

Run:  python scripts/build_map.py [boundary-file ...]

With no arguments it uses every .gpkg and .geojson file in inputs/boundaries/.
Download: ONS Open Geography Portal, "Local Planning Authorities (January 2026)
Boundaries UK BUC" as GeoPackage (.gpkg, British National Grid) or GeoJSON
(WGS84 longitude/latitude). See README.md.

What it does:
  - keeps only three properties per area: code (our LPA code, found through the
    ONS code in data/lpa.csv; blank outside England), name and nation
  - simplifies each outline (Douglas-Peucker) and rounds coordinates to 4
    decimal places, so the file stays under 2 MB
  - prints English councils in data/lpa.csv with no shape, and English shapes
    with no code.
  - writes data/other-planning-authority.csv: each development corporation (a
    separate planning authority inside or next to a council), whether we cover it,
    and which councils it borders (worked out from shared boundary points). The
    explorer shows these as notes ("applications here are decided by ..."). County councils (minerals and waste) overlap districts, so
    they are never drawn; the explorer lists them under the map instead.
Standard library only.
"""

import json
import re
import sqlite3
import struct
import sys
from pathlib import Path

from bng import to_wgs84
from common import DATA, INPUTS, ROOT, read_csv

OUT = ROOT / "docs" / "map" / "uk-lpa.geojson"
TOLERANCE = 0.0008      # degrees (about 60-90 m); raise it if the file is too big
TOLERANCE_M = 120       # the same in metres, for British National Grid files
NATIONS = {"E": "England", "W": "Wales", "S": "Scotland", "N": "Northern Ireland"}


def find_keys(props):
    """Find the ONS code and name properties (e.g. LPA23CD / LPA23NM, or LAD25CD / LAD25NM)."""
    code = next((k for k in props if re.fullmatch(r"(LPA|LAD)\d{2}CD", k, re.I)), None)
    name = next((k for k in props if re.fullmatch(r"(LPA|LAD)\d{2}NM", k, re.I)), None)
    if not code:
        raise SystemExit(f"Can't find an ONS code property (like LPA23CD) in: {', '.join(props)}")
    return code, name


def perpendicular(p, a, b):
    """Distance from point p to the line a-b (in degrees; fine for simplifying)."""
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
    return abs(dy * x - dx * y + x2 * y1 - y2 * x1) / (dx * dx + dy * dy) ** 0.5


def simplify(points, tol):
    """Douglas-Peucker: drop points that are closer than tol to the line between their neighbours."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        best, index = 0.0, None
        for i in range(start + 1, end):
            d = perpendicular(points[i], points[start], points[end])
            if d > best:
                best, index = d, i
        if index is not None and best > tol:
            keep[index] = True
            stack += [(start, index), (index, end)]
    return [p for p, k in zip(points, keep) if k]


def ring(points):
    """Simplify and round one ring; drop it if it collapses. Rings in British National
    Grid metres are simplified in metres first, then converted to longitude/latitude."""
    pts = [tuple(p[:2]) for p in points]
    if pts and abs(pts[0][0]) > 180:
        pts = [to_wgs84(x, y) for x, y in simplify(pts, TOLERANCE_M)]
    else:
        pts = simplify(pts, TOLERANCE)
    pts = [[round(x, 4), round(y, 4)] for x, y in pts]
    out = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
    if out and out[0] != out[-1]:
        out.append(out[0])
    return out if len(out) >= 4 else None


def geometry(geom):
    """Simplify a Polygon or MultiPolygon; tiny islands that collapse are dropped."""
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    kept = []
    for poly in polys:
        rings = [r for r in (ring(x) for x in poly) if r]
        if rings and rings[0]:
            kept.append(rings)
    if not kept:
        return None
    return {"type": "Polygon", "coordinates": kept[0]} if len(kept) == 1 else \
        {"type": "MultiPolygon", "coordinates": kept}


# ---------- reading a GeoPackage (an SQLite file) ----------

def wkb_polygons(buf, pos=0):
    """Read a WKB Polygon or MultiPolygon (2D, Z, M or ZM; only x and y are kept).
    Returns (list of polygons, next position)."""
    order = "<" if buf[pos] == 1 else ">"
    code = struct.unpack_from(order + "I", buf, pos + 1)[0]
    pos += 5
    kind, flavour = code % 1000, code // 1000            # ISO WKB: 1000s = Z, 2000s = M, 3000s = ZM
    dims = {0: 2, 1: 3, 2: 3, 3: 4}.get(flavour & 7, 2)
    if code & 0x80000000 or code & 0x40000000:           # older EWKB flags for Z / M
        kind = code & 0xFF
        dims = 2 + bool(code & 0x80000000) + bool(code & 0x40000000)
    if kind == 3:      # Polygon: rings of points
        nrings = struct.unpack_from(order + "I", buf, pos)[0]; pos += 4
        rings = []
        for _ in range(nrings):
            npts = struct.unpack_from(order + "I", buf, pos)[0]; pos += 4
            pts = struct.unpack_from(order + "%dd" % (dims * npts), buf, pos); pos += 8 * dims * npts
            rings.append([[pts[i], pts[i + 1]] for i in range(0, len(pts), dims)])
        return [rings], pos
    if kind == 6:      # MultiPolygon: several polygons
        n = struct.unpack_from(order + "I", buf, pos)[0]; pos += 4
        polys = []
        for _ in range(n):
            p, pos = wkb_polygons(buf, pos)
            polys += p
        return polys, pos
    raise SystemExit(f"Unsupported geometry type {code} in the GeoPackage")


def read_gpkg(path):
    """Features from a GeoPackage as GeoJSON-like dicts (coordinates in the file's own system)."""
    db = sqlite3.connect(str(path))
    table, geom_col = db.execute("SELECT table_name, column_name FROM gpkg_geometry_columns").fetchone()
    cols = [r[1] for r in db.execute(f"PRAGMA table_info('{table}')")]
    features = []
    for row in db.execute(f"SELECT * FROM '{table}'"):
        rec = dict(zip(cols, row))
        blob = rec.pop(geom_col)
        if not blob:
            continue
        flags = blob[3]
        envelope = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(flags >> 1) & 7]
        polys, _ = wkb_polygons(blob, 8 + envelope)
        geom = {"type": "MultiPolygon", "coordinates": polys}
        features.append({"type": "Feature", "properties": rec, "geometry": geom})
    return {"features": features}


def main():
    folder = INPUTS / "boundaries"
    files = [Path(a) for a in sys.argv[1:]] or sorted(list(folder.glob("*.gpkg")) + list(folder.glob("*.geojson")))
    if not files:
        raise SystemExit("No boundary file found. Put the ONS GeoJSON in inputs/boundaries/ (see README.md).")
    lpas = read_csv(DATA / "lpa.csv")
    by_ons = {r["ons-code"]: r for r in lpas if r["ons-code"]}
    # ONS codes change when planning powers move (for example to a development corporation),
    # so if a code isn't in data/lpa.csv, try the name instead and say so.
    from build_lpas import normalise
    by_name = {normalise(r["name"]): r for r in lpas}
    by_name_matches = []

    features, seen = [], set()
    corps, edges = [], {}   # development corporations, and boundary points of every English area
    for f in files:
        data = read_gpkg(f) if str(f).endswith(".gpkg") else json.loads(Path(f).read_text(encoding="utf-8"))
        code_key, name_key = find_keys(data["features"][0]["properties"])
        print(f"Reading {f} ({len(data['features'])} areas, codes in '{code_key}')")
        for feat in data["features"]:
            ons = feat["properties"][code_key]
            if ons in seen:
                continue  # the same area in two files
            if ons.startswith("E") and feat.get("geometry"):
                raw = feat["geometry"]["coordinates"]
                polys = [raw] if feat["geometry"]["type"] == "Polygon" else raw
                # rounded raw points; two areas sharing several points share a border
                edges[ons] = {(round(x, 5), round(y, 5)) for poly in polys for r in poly for x, y, *_ in r}
                shape_name = re.sub(r"\s+LPA$", "", str(feat["properties"].get(name_key, "")))
                if "development corporation" in shape_name.lower():
                    corps.append((ons, shape_name))
            geom = geometry(feat["geometry"]) if feat.get("geometry") else None
            if not geom:
                continue
            seen.add(ons)
            lpa = by_ons.get(ons)
            if not lpa and ons.startswith("E"):
                shape_name = re.sub(r"\s+LPA$", "", str(feat["properties"].get(name_key, "")))
                lpa = by_name.get(normalise(shape_name))
                if lpa and "development corporation" not in shape_name.lower():
                    by_name_matches.append(f"{lpa['code']:7} {lpa['name']}: boundary code {ons}, ours {lpa['ons-code']}")
                else:
                    lpa = None
            features.append({"type": "Feature", "properties": {
                "code": lpa["code"] if lpa else "",
                "name": lpa["name"] if lpa else feat["properties"].get(name_key, ons),
                "nation": NATIONS.get(ons[:1], "")}, "geometry": geom})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":"))
    OUT.write_text(text, encoding="utf-8")
    size = len(text.encode()) / 1e6
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(features)} areas, {size:.2f} MB"
          + ("  (over 2 MB: raise TOLERANCE)" if size > 2 else ""))

    # Which councils does each development corporation border?
    ons_to_code = {r["ons-code"]: r["code"] for r in lpas if r["ons-code"]}
    for line in by_name_matches:   # councils matched by name use the boundary file's code
        code, rest = line.split(None, 1)
        ons_to_code[rest.split("boundary code ")[1].split(",")[0]] = code
    rows = []
    for ons, name in sorted(corps, key=lambda c: c[1]):
        near = sorted(((len(edges[ons] & pts), o) for o, pts in edges.items()
                       if o != ons and len(edges[ons] & pts) >= 2), reverse=True)
        borders = [ons_to_code[o] for n, o in near if o in ons_to_code]
        rows.append({"name": name, "ons-code": ons, "code": ons_to_code.get(ons, ""),
                     "borders": ";".join(borders)})
    from common import write_csv
    write_csv(DATA / "other-planning-authority.csv", rows, ["name", "ons-code", "code", "borders"])
    print(f"\nWrote data/other-planning-authority.csv: {len(rows)} development corporations")
    for r in rows:
        print(f"  {r['name']}: {'covered as ' + r['code'] if r['code'] else 'not covered'}; borders {r['borders'] or '-'}")

    if by_name_matches:
        print(f"\n{len(by_name_matches)} councils matched by name because their ONS code has changed "
              "(update data/organisation.csv with python scripts/update_register.py when you can):")
        for line in by_name_matches:
            print("  " + line)
    drawn = {f["properties"]["code"] for f in features if f["properties"]["code"]}
    missing = [r for r in lpas if r["code"] not in drawn]
    print(f"\n{len(missing)} English councils have no shape (the explorer lists them under the map):")
    for r in missing:
        print(f"  {r['code']:7} {r['name']} ({r['type']})")
    nocode = [f["properties"]["name"] for f in features
              if f["properties"]["nation"] == "England" and not f["properties"]["code"]]
    if nocode:
        print(f"\n{len(nocode)} English shapes match no council in data/lpa.csv:")
        for n in nocode:
            print("  ", n)


if __name__ == "__main__":
    main()
