"""Cloud-free median composite over a date window (same-season comparison)."""
from __future__ import annotations
import warnings
import numpy as np


def median_composite(values: np.ndarray, valid: np.ndarray, min_obs: int = 2):
    """values, valid: arrays of shape (T, H, W).

    Returns (composite float32 (H, W), composite_valid bool (H, W)).
    A pixel is valid only if at least `min_obs` clear observations exist.
    """
    if values.shape != valid.shape:
        raise ValueError("values and valid must have the same shape")
    masked = np.where(valid & np.isfinite(values), values, np.nan)
    count = np.sum(~np.isnan(masked), axis=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        comp = np.nanmedian(masked, axis=0).astype("float32")
    ok = count >= min_obs
    comp[~ok] = np.nan
    return comp, ok
