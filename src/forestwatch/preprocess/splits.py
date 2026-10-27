"""Spatial block splits with a buffer, to prevent train/test leakage.

Random patch splits leak information because neighbouring patches look alike.
Here the image is cut into square blocks, each block is assigned to
train / validation / test, and train blocks touching a validation or test
block are dropped (label -1 = buffer).
"""
from __future__ import annotations
import math
import numpy as np
from scipy import ndimage

TRAIN, VAL, TEST, BUFFER = 0, 1, 2, -1


def block_shape(h: int, w: int, block: int):
    return math.ceil(h / block), math.ceil(w / block)


def assign_block_splits(n_rows: int, n_cols: int, fractions=(0.6, 0.2, 0.2), seed: int = 42,
                        buffer: int = 1, group: int = 1) -> np.ndarray:
    """Return an (n_rows, n_cols) int grid with TRAIN/VAL/TEST/BUFFER labels.

    `group` > 1 assigns splits to contiguous group x group tiles of blocks instead of
    single blocks. Without grouping, scattered val/test blocks sit next to almost every
    train block, so the buffer removes nearly all training data (e.g. 1 of 64 blocks kept).
    """
    g_rows, g_cols = -(-n_rows // group), -(-n_cols // group)
    n = g_rows * g_cols
    if n < 3:
        raise ValueError("Need at least 3 groups (train/val/test): use a smaller block_size_px or group_blocks")
    rng = np.random.default_rng(seed)
    order = rng.permutation(n)
    n_val = max(1, round(fractions[1] * n))
    n_test = max(1, round(fractions[2] * n))
    labels = np.full(n, TRAIN, dtype=np.int8)
    labels[order[:n_test]] = TEST
    labels[order[n_test:n_test + n_val]] = VAL
    grid = np.kron(labels.reshape(g_rows, g_cols), np.ones((group, group), dtype=np.int8))[:n_rows, :n_cols]
    if buffer > 0:
        non_train = grid != TRAIN
        near = ndimage.maximum_filter(non_train.astype(np.uint8), size=2 * buffer + 1) > 0
        grid = grid.copy()
        grid[(grid == TRAIN) & near] = BUFFER
    return grid


def pixel_split_map(h: int, w: int, block: int, grid: np.ndarray) -> np.ndarray:
    """Expand the block grid to a per-pixel split map of shape (h, w)."""
    full = np.kron(grid, np.ones((block, block), dtype=np.int8))
    return full[:h, :w]


def block_id_map(h: int, w: int, block: int) -> np.ndarray:
    n_rows, n_cols = block_shape(h, w, block)
    rows = np.arange(h) // block
    cols = np.arange(w) // block
    return (rows[:, None] * n_cols + cols[None, :]).astype(np.int32)


def check_no_leakage(grid: np.ndarray, buffer: int = 1) -> bool:
    """True if no TRAIN block lies within `buffer` blocks of a VAL/TEST block."""
    train = grid == TRAIN
    other = (grid == VAL) | (grid == TEST)
    near_other = ndimage.maximum_filter(other.astype(np.uint8), size=2 * buffer + 1) > 0
    return not bool(np.any(train & near_other))
