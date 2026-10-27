"""Patch sampling that respects the spatial split (numpy core + lazy torch Dataset)."""
from __future__ import annotations
import numpy as np


def _window_sums(ind: np.ndarray, patch: int, stride: int):
    H, W = ind.shape
    ii = np.pad(ind.astype("int64").cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    rows = np.arange(0, H - patch + 1, stride)
    cols = np.arange(0, W - patch + 1, stride)
    R, C = rows[:, None], cols[None, :]
    sums = ii[R + patch, C + patch] - ii[R, C + patch] - ii[R + patch, C] + ii[R, C]
    return rows, cols, sums


def valid_patch_origins(split_map: np.ndarray, split_label: int, patch: int, stride: int):
    """Origins (r, c) of patches lying ENTIRELY inside pixels of `split_label`."""
    rows, cols, sums = _window_sums(split_map == split_label, patch, stride)
    rr, cc = np.nonzero(sums == patch * patch)
    return [(int(rows[i]), int(cols[j])) for i, j in zip(rr, cc)]


def patch_positive_fraction(labels: np.ndarray, origins, patch: int) -> np.ndarray:
    return np.array([labels[r:r + patch, c:c + patch].mean() for r, c in origins], dtype="float32")


def sampling_weights(pos_frac: np.ndarray, oversample: float = 4.0) -> np.ndarray:
    return 1.0 + oversample * (pos_frac > 0).astype("float32")


def make_torch_dataset(X, y, origins, patch, augment=True, seed=0):
    import torch
    from torch.utils.data import Dataset

    class PatchDataset(Dataset):
        def __init__(self):
            self.rng = np.random.default_rng(seed)

        def __len__(self):
            return len(origins)

        def __getitem__(self, i):
            r, c = origins[i]
            xp = X[:, r:r + patch, c:c + patch]
            yp = y[r:r + patch, c:c + patch].astype("float32")
            if augment:
                k = int(self.rng.integers(0, 4))
                xp, yp = np.rot90(xp, k, axes=(1, 2)), np.rot90(yp, k)
                if self.rng.random() < 0.5:
                    xp, yp = xp[:, :, ::-1], yp[:, ::-1]
            return torch.from_numpy(np.ascontiguousarray(xp)), torch.from_numpy(np.ascontiguousarray(yp))
    return PatchDataset()
