"""Reflectance scaling and spectral indices."""
from __future__ import annotations
from datetime import date
import numpy as np

# Sentinel-2 processing baseline 04.00 (from about 25 Jan 2022) adds an offset of
# 1000 to the digital numbers. Verify against the asset metadata of your scenes.
BASELINE_04_START = date(2022, 1, 25)


def scale_reflectance(dn: np.ndarray, acquisition: date, quantification: float = 10000.0,
                      offset_dn: float | None = None) -> np.ndarray:
    """DN -> reflectance. `offset_dn` (in DN units, e.g. -1000) overrides the date rule when given."""
    offset = offset_dn if offset_dn is not None else (-1000.0 if acquisition >= BASELINE_04_START else 0.0)
    ref = (dn.astype("float32") + offset) / quantification
    return np.clip(ref, 0.0, 1.5)


def scale_with_catalog(dn: np.ndarray, scale: float, offset: float) -> np.ndarray:
    """reflectance = DN * scale + offset, exactly as the STAC raster:bands metadata of the asset states
    (typically scale 0.0001, offset -0.1 or 0)."""
    return np.clip(dn.astype("float32") * np.float32(scale) + np.float32(offset), 0.0, 1.5)


def _norm_diff(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    denom = a + b
    out = np.full(a.shape, np.nan, dtype="float32")
    ok = denom > 1e-6
    out[ok] = (a[ok] - b[ok]) / denom[ok]
    return out


def ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    return _norm_diff(nir, red)


def nbr(nir: np.ndarray, swir22: np.ndarray) -> np.ndarray:
    """Normalized Burn Ratio; drops sharply after fire or clearing."""
    return _norm_diff(nir, swir22)
