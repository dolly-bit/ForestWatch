"""Sentinel-1 radar cross-check (VH/VV backscatter change) for reviewed detections.

Idea: radar does not depend on clouds or NDVI, so it gives independent evidence. When vegetation is
removed, VH backscatter usually changes relative to the surroundings. We measure that change inside
each candidate MINUS the change in the surrounding ring, which cancels regional effects such as soil
moisture or season. Only scenes from ONE satellite track (relative orbit + direction) are comparable.

HONEST LIMITS: backscatter also changes with crop cycles, rain and soil moisture, so this is supporting
evidence, not ground truth. Use it to ask "do my real detections differ from my false ones?".
"""
from __future__ import annotations
import warnings
import numpy as np

NODATA = -32768.0


def clean_linear(a) -> np.ndarray:
    """Linear power with nodata / non-positive values set to NaN."""
    a = np.asarray(a, dtype="float32")
    return np.where(np.isfinite(a) & (a > 0), a, np.nan).astype("float32")


def to_db(linear) -> np.ndarray:
    a = np.asarray(linear, dtype="float32")
    out = np.full(a.shape, np.nan, dtype="float32")
    ok = np.isfinite(a) & (a > 0)
    out[ok] = 10.0 * np.log10(a[ok])
    return out


def mosaic(arrays) -> np.ndarray:
    """Fill gaps (NaN) of the first array with values from the others (adjacent frames, same date)."""
    out = arrays[0].copy()
    for a in arrays[1:]:
        m = np.isnan(out)
        out[m] = a[m]
    return out


def composite_db(series: np.ndarray) -> np.ndarray:
    """(T, H, W) linear power -> dB of the per-pixel median (robust against speckle)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        med = np.nanmedian(series, axis=0)
    return to_db(med)


def choose_track(counts_before: dict, counts_after: dict):
    """Pick the (relative_orbit, direction) with the most scenes in BOTH windows.
    Returns (key, min_count) or (None, 0)."""
    keys = set(counts_before) & set(counts_after)
    if not keys:
        return None, 0
    best = max(keys, key=lambda k: min(counts_before[k], counts_after[k]))
    return best, min(counts_before[best], counts_after[best])


def local_contrast(delta_db: np.ndarray, row: int, col: int, r_in: int = 3, r_out: int = 30) -> float:
    """Mean change inside a small window minus median change of the surrounding ring."""
    H, W = delta_db.shape
    if not (0 <= row < H and 0 <= col < W):
        return float("nan")
    r0, r1, c0, c1 = max(row - r_out, 0), min(row + r_out + 1, H), max(col - r_out, 0), min(col + r_out + 1, W)
    win = delta_db[r0:r1, c0:c1]
    rr, cc = np.ogrid[r0:r1, c0:c1]
    inner = (np.abs(rr - row) <= r_in) & (np.abs(cc - col) <= r_in)
    a, b = win[inner], win[~inner]
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < 5 or len(b) < 20:
        return float("nan")
    return float(a.mean() - np.median(b))


def auc(pos, neg) -> float:
    """Probability that a random 'pos' value exceeds a random 'neg' value (ties count half). 0.5 = no signal."""
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    gt = (pos[:, None] > neg[None, :]).sum()
    eq = (pos[:, None] == neg[None, :]).sum()
    return float((gt + 0.5 * eq) / (len(pos) * len(neg)))


def auc_ci(pos, neg, n_boot: int = 2000, seed: int = 0):
    rng = np.random.default_rng(seed)
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    vals = [auc(pos[rng.integers(0, len(pos), len(pos))], neg[rng.integers(0, len(neg), len(neg))])
            for _ in range(n_boot)]
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return float(lo), float(hi)


def radar_table(rows, delta_vh, delta_vv, transform, crs, r_in=3, r_out=30):
    """Add radar features to reviewed rows (needs lat/lon in each row; pyproj for the conversion)."""
    from .change.exclusions import lonlat_to_rowcol
    from .review import normalize_verdict
    out = []
    for r in rows:
        v = normalize_verdict(r.get("verdict"))
        if v not in ("y", "n") or not r.get("lat"):
            continue
        row, col = lonlat_to_rowcol(float(r["lon"]), float(r["lat"]), transform, crs)
        out.append({"id": r["id"], "verdict": v, "area_ha": r.get("area_ha"),
                    "dvh_rel_db": local_contrast(delta_vh, row, col, r_in, r_out),
                    "dvv_rel_db": local_contrast(delta_vv, row, col, r_in, r_out)})
    return out
