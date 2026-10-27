"""Turn hand-drawn polygons (GeoJSON from QGIS) into a boolean label raster.

Pure numpy + matplotlib, so it is testable without rasterio. Only reprojection
(when the file is not already in the stack CRS) needs pyproj.
Assumes a north-up grid (as produced by data/download.py).
"""
from __future__ import annotations
import json
import numpy as np
from matplotlib.path import Path as MplPath


def _reproject_ring(ring, src_crs, dst_crs):
    if src_crs == dst_crs:
        return ring
    from pyproj import Transformer  # lazy import
    tr = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    xs, ys = tr.transform([p[0] for p in ring], [p[1] for p in ring])
    return list(zip(xs, ys))


def _inside(ring, xs, ys):
    return MplPath(np.asarray(ring)[:, :2]).contains_points(np.column_stack([xs.ravel(), ys.ravel()])).reshape(xs.shape)


def polygon_mask(rings, transform, shape) -> np.ndarray:
    """rings[0] is the exterior, the rest are holes. transform = (a,b,c,d,e,f)."""
    a, b, c, d, e, f = transform
    if abs(b) > 1e-9 or abs(d) > 1e-9:
        raise ValueError("Only north-up grids are supported")
    h, w = shape
    pts = np.asarray(rings[0])
    c0 = int(np.floor((pts[:, 0].min() - c) / a)); c1 = int(np.ceil((pts[:, 0].max() - c) / a))
    r0 = int(np.floor((pts[:, 1].max() - f) / e)); r1 = int(np.ceil((pts[:, 1].min() - f) / e))
    c0, c1, r0, r1 = max(c0, 0), min(c1, w), max(r0, 0), min(r1, h)
    out = np.zeros((h, w), dtype=bool)
    if c0 >= c1 or r0 >= r1:
        return out                                   # polygon outside the grid
    cols, rows = np.meshgrid(np.arange(c0, c1), np.arange(r0, r1))
    xs, ys = c + a * (cols + 0.5), f + e * (rows + 0.5)   # pixel centres
    m = _inside(rings[0], xs, ys)
    for hole in rings[1:]:
        m &= ~_inside(hole, xs, ys)
    out[r0:r1, c0:c1] = m
    return out


def rasterize_geojson(geojson: dict, transform, shape, src_crs="EPSG:4326", dst_crs="EPSG:32643"):
    """Return (mask, n_polygons) for all Polygon / MultiPolygon features."""
    feats = geojson["features"] if geojson.get("type") == "FeatureCollection" else [geojson]
    mask = np.zeros(shape, dtype=bool); n = 0
    for ft in feats:
        g = ft.get("geometry", ft)
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]] if g["type"] == "Polygon" else []
        for poly in polys:
            rings = [_reproject_ring(r, src_crs, dst_crs) for r in poly]
            mask |= polygon_mask(rings, transform, shape); n += 1
    return mask, n


def load_geojson(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
