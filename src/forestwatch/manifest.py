"""Spatial split manifest: one row per block, frozen with a checksum so the test split cannot drift."""
from __future__ import annotations
import hashlib
from pathlib import Path
import numpy as np

from .preprocess.splits import assign_block_splits, block_shape, check_no_leakage, TRAIN, VAL, TEST, BUFFER

SPLIT_NAMES = {TRAIN: "train", VAL: "validation", TEST: "test", BUFFER: "buffer"}
COLUMNS = ["block_id", "row_block", "col_block", "px_row0", "px_row1", "px_col0", "px_col1",
           "min_x", "min_y", "max_x", "max_y", "crs", "split", "reason", "created_at"]


def build_manifest(split_cfg: dict, meta: dict, created_at: str = "") -> list[dict]:
    H, W, block = meta["height"], meta["width"], split_cfg["block_size_px"]
    n_rows, n_cols = block_shape(H, W, block)
    grid = assign_block_splits(n_rows, n_cols, tuple(split_cfg["fractions"]), split_cfg["seed"],
                               split_cfg["buffer_blocks"], split_cfg.get("group_blocks", 1))
    if not check_no_leakage(grid, split_cfg["buffer_blocks"]):
        raise ValueError("Split leaks: a train block touches a validation/test block")
    a, b, c, d, e, f = meta["transform"]
    reason = (f"grouped random assignment (seed={split_cfg['seed']}, group_blocks={split_cfg.get('group_blocks', 1)}, "
              f"fractions={list(split_cfg['fractions'])}); buffer={split_cfg['buffer_blocks']} block(s)")
    rows = []
    for r in range(n_rows):
        for cc in range(n_cols):
            r0, r1, c0, c1 = r * block, min((r + 1) * block, H), cc * block, min((cc + 1) * block, W)
            xs, ys = [c + a * c0, c + a * c1], [f + e * r0, f + e * r1]
            label = int(grid[r, cc])
            rows.append({"block_id": r * n_cols + cc, "row_block": r, "col_block": cc,
                         "px_row0": r0, "px_row1": r1, "px_col0": c0, "px_col1": c1,
                         "min_x": min(xs), "min_y": min(ys), "max_x": max(xs), "max_y": max(ys),
                         "crs": meta["crs"], "split": SPLIT_NAMES[label],
                         "reason": reason if label != BUFFER else "buffer: train block adjacent to validation/test",
                         "created_at": created_at})
    return rows


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
