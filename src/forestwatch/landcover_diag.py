"""Land-cover helpers: class names, per-row lookup, and a label-free detector diagnostic."""
from __future__ import annotations
import numpy as np

CLASS_NAMES = {10: "tree cover", 20: "shrubland", 30: "grassland", 40: "cropland", 50: "built-up",
               60: "bare/sparse", 70: "snow/ice", 80: "water", 90: "wetland", 95: "mangroves", 100: "moss/lichen",
               -1: "outside grid"}


def landcover_for_rows(rows, grid: np.ndarray, transform, crs) -> list[int]:
    """Class under each row's lat/lon (-1 if outside the grid or no coordinates)."""
    from .change.exclusions import lonlat_to_rowcol
    H, W = grid.shape
    out = []
    for r in rows:
        if not r.get("lat") or not r.get("lon"):
            out.append(-1)
            continue
        row, col = lonlat_to_rowcol(float(r["lon"]), float(r["lat"]), transform, crs)
        out.append(int(grid[row, col]) if (0 <= row < H and 0 <= col < W) else -1)
    return out


def ndvi_by_class(ndvi_before, valid, mask, grid, forest_ndvi_min) -> list[dict]:
    """For each land-cover class: how green it was before, and how much of it the detector flagged.
    Uses NO review labels."""
    total = int(mask.sum())
    rows = []
    for cls in np.unique(grid):
        m = grid == cls
        v = m & valid & np.isfinite(ndvi_before)
        n_valid = int(v.sum())
        if n_valid == 0:
            continue
        flagged = int((mask & m).sum())
        rows.append({"class": int(cls), "name": CLASS_NAMES.get(int(cls), "?"), "area_share": float(m.mean()),
                     "valid_pixels": n_valid,
                     "median_ndvi_before": float(np.median(ndvi_before[v])),
                     "share_ndvi_at_least_threshold": float((ndvi_before[v] >= forest_ndvi_min).mean()),
                     "flagged_share_of_class": flagged / n_valid,
                     "share_of_all_detections": (flagged / total) if total else None})
    return rows
