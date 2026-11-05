"""Convert British National Grid (EPSG:27700) eastings/northings to WGS84
longitude/latitude, with the standard library only.

Uses Ordnance Survey's published method ("A guide to coordinate systems in
Great Britain"): undo the Transverse Mercator projection on the Airy 1830
ellipsoid (OSGB36), then a Helmert transformation to WGS84. Accurate to a few
metres, which is far more than a national map needs.

You don't run this file; build_map.py uses it.
"""

from math import atan2, cos, degrees, radians, sin, sqrt, tan

# Airy 1830 ellipsoid and the National Grid projection
A, B = 6377563.396, 6356256.909
F0 = 0.9996012717
LAT0, LON0 = radians(49), radians(-2)
N0, E0 = -100000, 400000
E2 = 1 - (B * B) / (A * A)
N = (A - B) / (A + B)

# Helmert transformation OSGB36 -> WGS84
TX, TY, TZ = 446.448, -125.157, 542.060
S = 20.4894e-6
RX, RY, RZ = (radians(x / 3600) for x in (0.1502, 0.2470, 0.8421))
WA, WB = 6378137.000, 6356752.3142   # WGS84 ellipsoid


def _meridional_arc(lat):
    n, n2, n3 = N, N * N, N ** 3
    return B * F0 * (
        (1 + n + 5 / 4 * n2 + 5 / 4 * n3) * (lat - LAT0)
        - (3 * n + 3 * n2 + 21 / 8 * n3) * sin(lat - LAT0) * cos(lat + LAT0)
        + (15 / 8 * n2 + 15 / 8 * n3) * sin(2 * (lat - LAT0)) * cos(2 * (lat + LAT0))
        - 35 / 24 * n3 * sin(3 * (lat - LAT0)) * cos(3 * (lat + LAT0)))


def _to_osgb36(e, n):
    """Easting/northing -> latitude/longitude (radians) on the Airy ellipsoid."""
    lat, m = LAT0, 0.0
    while True:
        lat = (n - N0 - m) / (A * F0) + lat
        m = _meridional_arc(lat)
        if abs(n - N0 - m) < 0.00001:
            break
    s = sin(lat)
    nu = A * F0 / sqrt(1 - E2 * s * s)
    rho = A * F0 * (1 - E2) / (1 - E2 * s * s) ** 1.5
    eta2 = nu / rho - 1
    t, sec = tan(lat), 1 / cos(lat)
    vii = t / (2 * rho * nu)
    viii = t / (24 * rho * nu ** 3) * (5 + 3 * t * t + eta2 - 9 * t * t * eta2)
    ix = t / (720 * rho * nu ** 5) * (61 + 90 * t * t + 45 * t ** 4)
    x = sec / nu
    xi = sec / (6 * nu ** 3) * (nu / rho + 2 * t * t)
    xii = sec / (120 * nu ** 5) * (5 + 28 * t * t + 24 * t ** 4)
    xiia = sec / (5040 * nu ** 7) * (61 + 662 * t * t + 1320 * t ** 4 + 720 * t ** 6)
    de = e - E0
    return (lat - vii * de ** 2 + viii * de ** 4 - ix * de ** 6,
            LON0 + x * de - xi * de ** 3 + xii * de ** 5 - xiia * de ** 7)


def to_wgs84(e, n):
    """British National Grid easting/northing (metres) -> (longitude, latitude) in degrees."""
    lat, lon = _to_osgb36(e, n)
    # to cartesian on Airy
    s = sin(lat)
    nu = A / sqrt(1 - E2 * s * s)
    x, y, z = nu * cos(lat) * cos(lon), nu * cos(lat) * sin(lon), (1 - E2) * nu * s
    # Helmert
    x2 = TX + (1 + S) * x - RZ * y + RY * z
    y2 = TY + RZ * x + (1 + S) * y - RX * z
    z2 = TZ - RY * x + RX * y + (1 + S) * z
    # back to latitude/longitude on WGS84
    e2 = 1 - (WB * WB) / (WA * WA)
    p = sqrt(x2 * x2 + y2 * y2)
    lat = atan2(z2, p * (1 - e2))
    for _ in range(10):
        nu = WA / sqrt(1 - e2 * sin(lat) ** 2)
        lat = atan2(z2 + e2 * nu * sin(lat), p)
    return degrees(atan2(y2, x2)), degrees(lat)


if __name__ == "__main__":
    # Ordnance Survey's worked example check point (Caister water tower, approximately)
    print(to_wgs84(651409.903, 313177.270))   # about (1.7164, 52.6576)
