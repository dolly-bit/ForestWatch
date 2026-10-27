"""Numpy-only tests for the Phase 2 logic (no torch / rasterio / network needed)."""
import json
import tempfile
from pathlib import Path
import numpy as np

from forestwatch.change.seasonal import persistence_mask
from forestwatch.change.vectorize import mask_to_features, feature_bbox
from forestwatch.models.infer import window_starts, predict_full
from forestwatch.models.dataset import valid_patch_origins, patch_positive_fraction, sampling_weights
from forestwatch.preprocess.splits import assign_block_splits, pixel_split_map, TRAIN
from forestwatch.synthetic import make_scene_pair
from forestwatch.config import load_config
from forestwatch.pipeline import run_pipeline, feature_stack, load_window, N_CHANNELS
from forestwatch.data.stack_io import save_stack

ROOT = Path(__file__).resolve().parents[1]
TRANSFORM = (10.0, 0.0, 500000.0, 0.0, -10.0, 3000000.0)


def test_persistence_keeps_real_clearing_and_drops_transient_drop():
    before = np.full((20, 20), 0.7, "float32")
    series = np.full((5, 20, 20), 0.7, "float32")
    series[:, 2:8, 2:8] = 0.2          # real: low on every date
    series[0, 12:18, 12:18] = 0.2      # transient: low on one date only
    valid = np.ones_like(series, bool)
    keep = persistence_mask(before, series, valid, 0.25, 0.6, 2)
    assert keep[4, 4] and not keep[15, 15] and not keep[0, 0]


def test_persistence_requires_enough_clear_observations():
    before = np.full((4, 4), 0.7, "float32")
    series = np.full((3, 4, 4), 0.2, "float32")
    valid = np.zeros_like(series, bool); valid[0] = True   # only one clear date
    assert not persistence_mask(before, series, valid, 0.25, 0.6, 2).any()


def test_vectorize_square_position_and_area():
    mask = np.zeros((40, 40), bool); mask[10:20, 5:15] = True       # 10x10 px
    feats = mask_to_features(mask, TRANSFORM, "EPSG:32643", score=np.full((40, 40), 0.8),
                             to_crs=None, resolution_m=10.0)
    assert len(feats) == 1
    f = feats[0]
    assert f["properties"]["n_pixels"] == 100 and abs(f["properties"]["area_ha"] - 1.0) < 1e-9
    assert abs(f["properties"]["confidence"] - 0.8) < 1e-9
    x0, y0, x1, y1 = feature_bbox(f)
    assert abs(x0 - 500050) < 6 and abs(x1 - 500150) < 6          # cols 5..15 -> x 500050..500150
    assert abs(y1 - 2999900) < 6 and abs(y0 - 2999800) < 6        # rows 10..20 -> y 2999900..2999800
    ring = f["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1] and len(ring) >= 4


def test_window_starts_cover_edges():
    for n in (64, 65, 100, 129):
        s = window_starts(n, 64, 32)
        assert s[0] == 0 and s[-1] == n - 64
    try:
        window_starts(30, 64, 32); assert False
    except ValueError:
        pass


def test_predict_full_reproduces_channel_with_overlaps():
    rng = np.random.default_rng(0)
    X = rng.random((3, 100, 90)).astype("float32")
    out = predict_full(lambda b: b[:, 0], X, 32, 16, batch_size=5)
    assert np.allclose(out, X[0], atol=1e-6)


def test_patches_stay_inside_their_split():
    grid = assign_block_splits(8, 8, seed=1, buffer=1, group=2)
    sm = pixel_split_map(8 * 32, 8 * 32, 32, grid)
    origins = valid_patch_origins(sm, TRAIN, 32, 16)
    assert origins
    for r, c in origins:
        assert (sm[r:r + 32, c:c + 32] == TRAIN).all()
    y = np.zeros(sm.shape, bool); r0, c0 = origins[0]; y[r0, c0] = True
    frac = patch_positive_fraction(y, origins, 32)
    w = sampling_weights(frac, 4.0)
    assert w[0] == 5.0 and w.min() == 1.0


def _ndvi_to_bands(ndvi):
    red = np.full_like(ndvi, 0.10, dtype="float32")
    nir = (red * (1 + ndvi) / (1 - ndvi)).astype("float32")
    return red, nir, np.full_like(red, 0.2)


def _write_fake_stacks(root, scene, after_dates=4):
    h, w = scene["ndvi_before"].shape
    meta = {"scene_id": "fake", "date": "2022-11-01", "crs": "EPSG:32643", "transform": list(TRANSFORM),
            "width": w, "height": h, "valid_fraction": 1.0}
    rng = np.random.default_rng(0)
    for name, key, n in (("before", "ndvi_before", 3), ("after", "ndvi_after", after_dates)):
        for i in range(n):
            nd = np.clip(scene[key] + 0.01 * rng.standard_normal((h, w)), -0.5, 0.95).astype("float32")
            red, nir, swir = _ndvi_to_bands(nd)
            valid = scene["valid_before"] if name == "before" else scene["valid_after"]
            save_stack(Path(root) / "data" / "stacks" / name / f"2022-11-0{i + 1}_fake.npz",
                       {"red": red, "nir": nir, "swir22": swir, "valid": valid}, {**meta, "date": f"2022-11-0{i + 1}"})


def test_end_to_end_pipeline_on_fake_stacks():
    scene = make_scene_pair(256, 256, seed=3, season_dip=0.0, cloud_blobs=2)
    with tempfile.TemporaryDirectory() as tmp:
        _write_fake_stacks(tmp, scene)
        cfg = load_config(ROOT / "configs" / "aravalli.yaml")
        cfg["region"]["output_crs"] = "EPSG:32643"               # skip reprojection (no pyproj needed)
        res = run_pipeline(cfg, tmp, "baseline")
        truth = scene["truth"]
        tp = (res["mask"] & truth).sum()
        assert tp / truth.sum() > 0.9                              # finds the clearings
        assert (res["mask"] & ~truth).sum() / max(res["mask"].sum(), 1) < 0.05   # few false alarms
        assert len(res["features"]) > 0
        f = res["features"][0]
        assert f["geometry"]["type"] == "Polygon" and 0.0 <= f["properties"]["confidence"] <= 1.0
        before, after = load_window(tmp, "before"), load_window(tmp, "after")
        X, valid = feature_stack(before, after)
        assert X.shape == (N_CHANNELS, 256, 256) and X.dtype == np.float32 and np.isfinite(X).all()
        json.dumps(res["features"])                                # must be JSON serialisable


def test_grouped_split_keeps_enough_training_blocks_and_no_leakage():
    from forestwatch.preprocess.splits import check_no_leakage, TEST, VAL
    g = assign_block_splits(16, 16, (0.6, 0.2, 0.2), seed=42, buffer=1, group=4)
    assert check_no_leakage(g, 1)
    assert (g == TRAIN).mean() > 0.35 and (g == TEST).any() and (g == VAL).any()
    scattered = assign_block_splits(16, 16, (0.6, 0.2, 0.2), seed=42, buffer=1, group=1)
    assert (scattered == TRAIN).mean() < 0.1       # documents why grouping is needed
