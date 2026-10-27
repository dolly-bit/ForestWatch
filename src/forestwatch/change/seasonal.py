"""Seasonal / transient-change filter.

A real clearing keeps NDVI low on (almost) every clear 'after' date. Dry-season
leaf drop, harvest, haze or noise usually does not. So a pixel is kept only if
the NDVI drop (vs the 'before' composite) appears on at least `min_frac` of its
clear 'after' observations.
"""
from __future__ import annotations
import numpy as np


def persistence_mask(ndvi_before, ndvi_after_series, valid_series,
                     drop_min=0.25, min_frac=0.6, min_obs=2) -> np.ndarray:
    """ndvi_before: (H, W); ndvi_after_series, valid_series: (T, H, W)."""
    ok = valid_series & np.isfinite(ndvi_after_series) & np.isfinite(ndvi_before)[None]
    with np.errstate(invalid="ignore"):
        dropped = (ndvi_before[None] - ndvi_after_series) >= drop_min
    n_valid = ok.sum(axis=0)
    n_drop = (dropped & ok).sum(axis=0)
    frac = np.zeros(n_valid.shape, dtype="float32")
    np.divide(n_drop, n_valid, out=frac, where=n_valid > 0)
    return (n_valid >= min_obs) & (frac >= min_frac)
