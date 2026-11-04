"""Chip geometry in lon/lat: Google Maps links, KML for Google Earth, GeoJSON. Needs pyproj (lazy)."""
from __future__ import annotations
from xml.sax.saxutils import escape
import numpy as np


def _to_lonlat(xs, ys, crs):
    from pyproj import Transformer
    lon, lat = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform(np.asarray(xs, float), np.asarray(ys, float))
    return [float(v) for v in np.atleast_1d(lon)], [float(v) for v in np.atleast_1d(lat)]


def polygon_lonlat(min_x, min_y, max_x, max_y, crs) -> list[list[float]]:
    lon, lat = _to_lonlat([min_x, max_x, max_x, min_x, min_x], [max_y, max_y, min_y, min_y, max_y], crs)
    return [[round(a, 7), round(b, 7)] for a, b in zip(lon, lat)]


def chip_bounds_xy(row, transform):
    a, b, c, d, e, f = transform
    r0, r1, c0, c1 = (int(row[k]) for k in ("chip_row0", "chip_row1", "chip_col0", "chip_col1"))
    xs, ys = [c + a * c0, c + a * c1], [f + e * r0, f + e * r1]
    return min(xs), min(ys), max(xs), max(ys)


def chip_ring(row, transform, crs):
    return polygon_lonlat(*chip_bounds_xy(row, transform), crs)


def chip_center(row, transform, crs):
    x0, y0, x1, y1 = chip_bounds_xy(row, transform)
    lon, lat = _to_lonlat([(x0 + x1) / 2], [(y0 + y1) / 2], crs)
    return round(lat[0], 6), round(lon[0], 6)


def maps_link(lat, lon, zoom: int = 17) -> str:
    return f"https://www.google.com/maps?q={lat},{lon}&t=k&z={zoom}"


def to_kml(rows, transform, crs, name: str = "ForestWatch chips") -> str:
    """One square per chip, named by unit id (no model information), for Google Earth (Projects > Import KML)."""
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
             f"<name>{escape(name)}</name>",
             '<Style id="chip"><LineStyle><color>ff00ffff</color><width>3</width></LineStyle>'
             '<PolyStyle><fill>0</fill></PolyStyle></Style>']
    for r in rows:
        ring = chip_ring(r, transform, crs)
        coords = " ".join(f"{lon},{lat},0" for lon, lat in ring)
        parts.append(f"<Placemark><name>{escape(str(r['unit_id']))}</name><styleUrl>#chip</styleUrl><Polygon>"
                     f"<outerBoundaryIs><LinearRing><coordinates>{coords}</coordinates></LinearRing></outerBoundaryIs>"
                     f"</Polygon></Placemark>")
    parts.append("</Document></kml>")
    return "\n".join(parts)


def labels_geojson(rows, transform, crs, properties) -> dict:
    feats = []
    for r in rows:
        feats.append({"type": "Feature",
                      "geometry": {"type": "Polygon", "coordinates": [chip_ring(r, transform, crs)]},
                      "properties": {k: r.get(k, "") for k in properties}})
    return {"type": "FeatureCollection", "features": feats}
