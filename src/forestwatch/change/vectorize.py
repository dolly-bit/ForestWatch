"""Turn a boolean change mask into GeoJSON polygon features.

Uses skimage contours (no rasterio/shapely needed). Holes inside a patch are
ignored (documented simplification). Contours follow pixel edges approximately.
"""
from __future__ import annotations
import numpy as np
from scipy import ndimage
from skimage import measure

EIGHT = np.ones((3, 3), dtype=int)


def _to_map(rows, cols, transform):
    a, b, c, d, e, f = transform
    return c + a * (cols + 0.5), f + e * (rows + 0.5)          # pixel centres


def _reproject(xs, ys, src_crs, dst_crs):
    if dst_crs is None or src_crs == dst_crs:
        return xs, ys
    from pyproj import Transformer                              # lazy import
    return Transformer.from_crs(src_crs, dst_crs, always_xy=True).transform(xs, ys)


def mask_to_features(mask, transform, crs, score=None, to_crs=None,
                     resolution_m=10.0, min_pixels=1):
    """Return a list of GeoJSON Feature dicts, one per connected component."""
    labeled, _ = ndimage.label(mask, structure=EIGHT)
    feats = []
    for i, sl in enumerate(ndimage.find_objects(labeled), start=1):
        comp = labeled[sl] == i
        n_px = int(comp.sum())
        if n_px < min_pixels:
            continue
        r0, c0 = sl[0].start, sl[1].start
        padded = np.pad(comp, 1).astype(float)
        contours = measure.find_contours(padded, 0.5)
        if contours:
            ring = max(contours, key=len)
            ring = measure.approximate_polygon(ring, tolerance=0.7)
            rows, cols = ring[:, 0] - 1 + r0, ring[:, 1] - 1 + c0
        else:
            rows = cols = np.array([])
        if len(rows) < 4:                                       # tiny blob: use its bounding box
            rows = np.array([r0 - .5, r0 - .5, sl[0].stop - .5, sl[0].stop - .5, r0 - .5])
            cols = np.array([c0 - .5, sl[1].stop - .5, sl[1].stop - .5, c0 - .5, c0 - .5])
        xs, ys = _to_map(rows, cols, transform)
        xs, ys = _reproject(np.asarray(xs), np.asarray(ys), crs, to_crs)
        coords = [[float(x), float(y)] for x, y in zip(xs, ys)]
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        conf = float(np.nanmean(score[sl][comp])) if score is not None else None
        feats.append({"type": "Feature",
                      "geometry": {"type": "Polygon", "coordinates": [coords]},
                      "properties": {"id": i, "n_pixels": n_px,
                                     "area_ha": n_px * resolution_m ** 2 / 10000.0,
                                     "confidence": conf}})
    return feats


def feature_bbox(feature):
    pts = np.array(feature["geometry"]["coordinates"][0])
    return float(pts[:, 0].min()), float(pts[:, 1].min()), float(pts[:, 0].max()), float(pts[:, 1].max())
