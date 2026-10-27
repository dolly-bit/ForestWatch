"""Pixel-, polygon- and block-bootstrap metrics for the change class."""
from __future__ import annotations
import numpy as np
from scipy import ndimage

EIGHT = np.ones((3, 3), dtype=int)


def confusion(pred: np.ndarray, truth: np.ndarray, region: np.ndarray | None = None) -> dict:
    if region is None:
        region = np.ones_like(pred, dtype=bool)
    p, t = pred[region].astype(bool), truth[region].astype(bool)
    return {"tp": int(np.sum(p & t)), "fp": int(np.sum(p & ~t)),
            "fn": int(np.sum(~p & t)), "tn": int(np.sum(~p & ~t))}


def prf(c: dict) -> dict:
    tp, fp, fn = c["tp"], c["fp"], c["fn"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "iou": iou}


def pixel_metrics(pred, truth, region=None) -> dict:
    return prf(confusion(pred, truth, region))


def polygon_metrics(pred, truth, region=None, min_overlap: float = 0.1) -> dict:
    """Object-level scores: a true patch counts as detected if at least
    `min_overlap` of its pixels are flagged; a predicted blob counts as correct
    if at least `min_overlap` of its pixels fall on a true patch."""
    if region is None:
        region = np.ones_like(pred, dtype=bool)
    p, t = pred.astype(bool) & region, truth.astype(bool) & region
    t_lab, n_t = ndimage.label(t, structure=EIGHT)
    p_lab, n_p = ndimage.label(p, structure=EIGHT)
    detected = sum(1 for i in range(1, n_t + 1) if p[t_lab == i].mean() >= min_overlap)
    correct = sum(1 for i in range(1, n_p + 1) if t[p_lab == i].mean() >= min_overlap)
    return {"true_patches": n_t, "detected": detected,
            "detection_rate": detected / n_t if n_t else float("nan"),
            "pred_blobs": n_p, "correct_blobs": correct,
            "blob_precision": correct / n_p if n_p else float("nan")}


def block_bootstrap_f1(pred, truth, pixel_split, block_ids, split_label: int,
                       n_boot: int = 1000, seed: int = 0):
    """95% bootstrap interval of F1, resampling whole blocks (not pixels)."""
    region = pixel_split == split_label
    ids = np.unique(block_ids[region])
    per_block = []
    for b in ids:
        m = region & (block_ids == b)
        c = confusion(pred, truth, m)
        per_block.append((c["tp"], c["fp"], c["fn"]))
    arr = np.array(per_block, dtype=float)
    rng = np.random.default_rng(seed)
    f1s = []
    for _ in range(n_boot):
        s = arr[rng.integers(0, len(arr), len(arr))].sum(axis=0)
        f1s.append(prf({"tp": s[0], "fp": s[1], "fn": s[2]})["f1"])
    lo, hi = np.percentile(f1s, [2.5, 97.5])
    return float(lo), float(hi)
