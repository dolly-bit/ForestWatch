"""NDVI-difference baseline for vegetation-loss detection.

This is the baseline every later model (U-Net, bi-temporal) must beat.
"""
from __future__ import annotations
import numpy as np
from scipy import ndimage

EIGHT_CONNECTED = np.ones((3, 3), dtype=int)


def remove_small_components(mask: np.ndarray, min_pixels: int) -> np.ndarray:
    """Drop connected blobs smaller than the minimum mapping unit."""
    labeled, n = ndimage.label(mask, structure=EIGHT_CONNECTED)
    if n == 0:
        return mask.copy()
    sizes = ndimage.sum(mask, labeled, index=np.arange(1, n + 1))
    keep = np.zeros(n + 1, dtype=bool)
    keep[1:] = sizes >= min_pixels
    return keep[labeled]


def detect_change(ndvi_before, ndvi_after, valid_before, valid_after,
                  forest_ndvi_min=0.40, ndvi_drop_min=0.25, min_area_pixels=10) -> np.ndarray:
    """Boolean map of candidate newly cleared pixels.

    A pixel is flagged when it was vegetated before, both dates are cloud-free,
    and NDVI fell by at least `ndvi_drop_min`. Small blobs are removed.
    """
    valid = valid_before & valid_after & np.isfinite(ndvi_before) & np.isfinite(ndvi_after)
    drop = ndvi_before - ndvi_after
    cand = valid & (ndvi_before >= forest_ndvi_min) & (drop >= ndvi_drop_min)
    return remove_small_components(cand, min_area_pixels)


def components_summary(mask: np.ndarray, pixel_area_m2: float = 100.0) -> list[dict]:
    """Area (hectares) and bounding box of every flagged blob."""
    labeled, n = ndimage.label(mask, structure=EIGHT_CONNECTED)
    out = []
    for i, sl in enumerate(ndimage.find_objects(labeled), start=1):
        area_px = int(np.sum(labeled[sl] == i))
        out.append({"id": i, "area_ha": area_px * pixel_area_m2 / 10000.0,
                    "rows": (sl[0].start, sl[0].stop), "cols": (sl[1].start, sl[1].stop)})
    return out
