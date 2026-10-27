"""Cloud / shadow masking from the Sentinel-2 L2A Scene Classification Layer (SCL).

SCL classes: 0 no data, 1 saturated/defective, 2 dark area, 3 cloud shadow,
4 vegetation, 5 not vegetated, 6 water, 7 unclassified, 8 cloud (medium prob.),
9 cloud (high prob.), 10 thin cirrus, 11 snow/ice.
"""
from __future__ import annotations
import numpy as np
from scipy import ndimage

DEFAULT_VALID = (4, 5, 6, 7)


def valid_mask_from_scl(scl: np.ndarray, valid_classes=DEFAULT_VALID, dilate_px: int = 1) -> np.ndarray:
    """True where a pixel is usable. Invalid areas are dilated to catch cloud edges."""
    valid = np.isin(scl, list(valid_classes))
    if dilate_px > 0:
        invalid = ndimage.binary_dilation(~valid, structure=np.ones((3, 3), dtype=bool), iterations=dilate_px)
        valid = ~invalid
    return valid


def valid_fraction(valid: np.ndarray) -> float:
    return float(valid.mean())
