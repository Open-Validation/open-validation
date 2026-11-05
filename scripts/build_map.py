"""Stage C: build the map file docs/map/uk-lpa.geojson from the boundary download.

Run:  python scripts/build_map.py [boundary-file.geojson ...]

With no arguments it uses every .geojson file in inputs/boundaries/.
Download: ONS Open Geography Portal, "Local Planning Authorities (April 20XX)
Boundaries UK BUC" (GeoJSON, WGS84 longitude/latitude). See README.md.

What it does:
  - keeps only three properties per area: code (our LPA code, found through the
    ONS code in data/lpa.csv; blank outside England), name and nation
  - simplifies each outline (Douglas-Peucker) and rounds coordinates to 4
    decimal places, so the file stays under 2 MB
  - prints English councils in data/lpa.csv with no shape, and English shapes
    with no code. County councils (minerals and waste) overlap districts, so
    they are never drawn; the explorer lists them under the map instead.
Standard library only.
"""

import json
import re
import sys
from pathlib import Path

from common import DATA, INPUTS, ROOT, read_csv

OUT = ROOT / "docs" / "map" / "uk-lpa.geojson"
TOLERANCE = 0.0008      # degrees (about 60-90 m); raise it if the file is too big
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
    """Simplify and round one ring; drop it if it collapses."""
    if points and abs(points[0][0]) > 180:
        raise SystemExit("The coordinates look like British National Grid (metres). "
                         "Download the GeoJSON in WGS84 (longitude/latitude) instead.")
    pts = [[round(x, 4), round(y, 4)] for x, y in simplify([tuple(p[:2]) for p in points], TOLERANCE)]
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


def main():
    files = [Path(a) for a in sys.argv[1:]] or sorted((INPUTS / "boundaries").glob("*.geojson"))
    if not files:
        raise SystemExit("No boundary file found. Put the ONS GeoJSON in inputs/boundaries/ (see README.md).")
    lpas = read_csv(DATA / "lpa.csv")
    by_ons = {r["ons-code"]: r for r in lpas if r["ons-code"]}

    features, seen = [], set()
    for f in files:
        data = json.loads(Path(f).read_text(encoding="utf-8"))
        code_key, name_key = find_keys(data["features"][0]["properties"])
        print(f"Reading {f} ({len(data['features'])} areas, codes in '{code_key}')")
        for feat in data["features"]:
            ons = feat["properties"][code_key]
            if ons in seen:
                continue  # the same area in two files
            geom = geometry(feat["geometry"]) if feat.get("geometry") else None
            if not geom:
                continue
            seen.add(ons)
            lpa = by_ons.get(ons)
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
