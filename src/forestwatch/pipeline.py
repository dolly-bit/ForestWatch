"""Shared pipeline used by the scripts AND the backend worker.

stacks on disk -> same-season composites -> (baseline | U-Net) -> seasonal filter
-> small-blob removal -> GeoJSON polygons.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np

from .data.stack_io import load_stack
from .preprocess.indices import ndvi as ndvi_fn
from .preprocess.composite import median_composite
from .preprocess.splits import assign_block_splits, pixel_split_map, block_id_map, block_shape
from .change.baseline import detect_change, remove_small_components
from .change.seasonal import persistence_mask
from .change.vectorize import mask_to_features
from .change.exclusions import exclusion_mask

BANDS = ("red", "nir", "swir22")
N_CHANNELS = 13          # 4 before + 4 after + 4 difference + 1 validity


def load_window(root, name: str, min_obs: int = 2) -> dict:
    """Load every stack in data/stacks/<name>/ and build median composites."""
    files = sorted((Path(root) / "data" / "stacks" / name).glob("*.npz"))
    if not files:
        raise FileNotFoundError(f"No stacks in data/stacks/{name}. Run search_scenes.py and build_stacks.py first.")
    lists = {k: [] for k in (*BANDS, "ndvi", "valid")}
    meta = None
    for f in files:
        arr, m = load_stack(f)
        meta = meta or m
        for k in BANDS:
            lists[k].append(arr[k])
        lists["ndvi"].append(ndvi_fn(arr["nir"], arr["red"]))
        lists["valid"].append(arr["valid"])
    valid_s = np.stack(lists["valid"])
    ndvi_s = np.stack(lists["ndvi"])
    out = {"n_dates": len(files), "meta": meta, "ndvi_series": ndvi_s, "valid_series": valid_s}
    for k in (*BANDS, "ndvi"):
        comp, ok = median_composite(np.stack(lists[k]), valid_s, min_obs)
        out[k] = comp
        if k == "ndvi":
            out["valid"] = ok
    return out


def feature_stack(before: dict, after: dict):
    """(13, H, W) float32 model input and the joint validity mask."""
    valid = before["valid"] & after["valid"]
    keys = (*BANDS, "ndvi")
    chans = [d[k] for d in (before, after) for k in keys] + [after[k] - before[k] for k in keys]
    X = np.nan_to_num(np.stack(chans).astype("float32"), nan=0.0)
    X *= valid[None]
    return np.concatenate([X, valid[None].astype("float32")]), valid


def split_maps(cfg: dict, shape):
    s = cfg["split"]
    H, W = shape
    grid = assign_block_splits(*block_shape(H, W, s["block_size_px"]), tuple(s["fractions"]),
                               s["seed"], s["buffer_blocks"], s.get("group_blocks", 1))
    return pixel_split_map(H, W, s["block_size_px"], grid), block_id_map(H, W, s["block_size_px"])


def run_pipeline(cfg: dict, root, method: str = "baseline", seasonal: bool | None = None,
                 checkpoint=None, return_windows: bool = False) -> dict:
    root = Path(root)
    sc = cfg.get("seasonal", {})
    min_obs = cfg["cloud_mask"]["min_valid_observations"]
    before, after = load_window(root, "before", min_obs), load_window(root, "after", min_obs)
    b = cfg["baseline"]

    if method == "baseline":
        mask = detect_change(before["ndvi"], after["ndvi"], before["valid"], after["valid"],
                             b["forest_ndvi_min"], b["ndvi_drop_min"], b["min_area_pixels"])
        # heuristic (uncalibrated) score: size of the NDVI drop
        score = np.nan_to_num(np.clip((before["ndvi"] - after["ndvi"]) / 0.6, 0, 1))
    elif method == "unet":
        from .models.infer import load_checkpoint, predict_full
        ckpt = Path(checkpoint or root / cfg["model"]["checkpoint"])
        if not ckpt.exists():
            raise FileNotFoundError(f"No trained model at {ckpt}. Run scripts/train_unet.py first.")
        predict_fn, ck = load_checkpoint(ckpt)
        X, valid = feature_stack(before, after)
        score = predict_full(predict_fn, X, cfg["model"]["patch_size"], cfg["model"]["stride"])
        mask = remove_small_components((score >= ck["threshold"]) & valid, b["min_area_pixels"])
    else:
        raise ValueError(f"Unknown method: {method}")

    use_seasonal = sc.get("enabled", True) if seasonal is None else seasonal
    if use_seasonal:
        keep = persistence_mask(before["ndvi"], after["ndvi_series"], after["valid_series"],
                                b["ndvi_drop_min"], sc.get("min_persistence", 0.6), sc.get("min_observations", 2))
        mask = remove_small_components(mask & keep, b["min_area_pixels"])

    meta = after["meta"]
    excluded = exclusion_mask(cfg, root, meta, mask.shape)       # e.g. cropland: crop cycles mimic vegetation loss
    if excluded.any():
        mask = remove_small_components(mask & ~excluded, b["min_area_pixels"])
    feats = mask_to_features(mask, tuple(meta["transform"]), meta["crs"], score,
                             cfg["region"].get("output_crs", "EPSG:4326"),
                             cfg["region"]["resolution_m"], b["min_area_pixels"])
    out = {"mask": mask, "score": score, "features": feats, "meta": meta,
           "valid": before["valid"] & after["valid"], "method": method, "seasonal": bool(use_seasonal)}
    if return_windows:
        out["windows"] = (before, after)
    return out
