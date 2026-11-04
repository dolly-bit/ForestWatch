"""Sampling frame: every full chip on the prediction grid, with its block, split, baseline status and landscape group."""
from __future__ import annotations
import numpy as np

from .blocks import region_for


def landcover_group(cls: int, groups: dict) -> str:
    for name, classes in groups.items():
        if int(cls) in classes:
            return name
    return "other"


def build_frame(shape, chip_px: int, block_px: int, manifest_rows, mask, drop, valid, lc_grid, params, groups) -> list[dict]:
    """mask: baseline detections; drop: NDVI before minus after (NaN where unknown); valid: both dates clear;
    lc_grid: land-cover classes on the same grid."""
    if block_px % chip_px:
        raise ValueError(f"chip_px ({chip_px}) must divide block_size_px ({block_px}) so chips never straddle two splits")
    H, W = shape
    for name, a in (("mask", mask), ("drop", drop), ("valid", valid), ("land cover", lc_grid)):
        if a.shape != (H, W):
            raise ValueError(f"{name} has shape {a.shape}, expected {(H, W)}: grids do not match")
    blocks = {(int(r["row_block"]), int(r["col_block"])): r for r in manifest_rows}
    n_br = max(k[0] for k in blocks) + 1
    n_bc = max(k[1] for k in blocks) + 1
    rows = []
    for i in range(H // chip_px):
        for j in range(W // chip_px):
            r0, c0 = i * chip_px, j * chip_px
            sl = (slice(r0, r0 + chip_px), slice(c0, c0 + chip_px))
            b = blocks[(r0 // block_px, c0 // block_px)]
            v = valid[sl]
            valid_fraction = float(v.mean())
            flagged_px = int(mask[sl].sum())
            ok = v & np.isfinite(drop[sl])
            drop_p95 = float(np.percentile(drop[sl][ok], 95)) if ok.any() else float("nan")
            if flagged_px >= params["min_flagged_px"]:
                status = "flagged"
            elif np.isfinite(drop_p95) and drop_p95 >= params["near_miss_drop"]:
                status = "unflagged_near_miss"
            else:
                status = "unflagged_quiet"
            lc = int(np.bincount(lc_grid[sl].astype(int).ravel()).argmax())
            group = landcover_group(lc, groups)
            reason = ""
            if b["split"] == "buffer":
                reason = "buffer_block"
            elif valid_fraction < params["min_valid_fraction"]:
                reason = "poor_observation"
            rows.append({"unit_id": f"C{i:03d}_{j:03d}", "block_id": int(b["block_id"]), "split": b["split"],
                         "region": region_for(int(b["row_block"]), int(b["col_block"]), n_br, n_bc),
                         "chip_row0": r0, "chip_row1": r0 + chip_px, "chip_col0": c0, "chip_col1": c0 + chip_px,
                         "baseline_status": status, "landcover_class": lc, "landcover_group": group,
                         "stratum": f"{status}|{group}", "valid_fraction": round(valid_fraction, 4),
                         "flagged_px": flagged_px, "drop_p95": "" if np.isnan(drop_p95) else round(drop_p95, 4),
                         "eligible": "no" if reason else "yes", "exclusion_reason": reason,
                         "selection_method": "", "selection_probability": "", "geometry_path": "", "notes": ""})
    return rows


def stratum_table(frame_rows) -> dict:
    """{split: {stratum: eligible chip count}}"""
    out: dict = {}
    for r in frame_rows:
        if r["eligible"] == "yes":
            out.setdefault(r["split"], {}).setdefault(r["stratum"], 0)
            out[r["split"]][r["stratum"]] += 1
    return out
