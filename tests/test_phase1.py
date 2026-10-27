import numpy as np
from datetime import date
from forestwatch.preprocess.cloudmask import valid_mask_from_scl
from forestwatch.preprocess.indices import ndvi, scale_reflectance
from forestwatch.preprocess.composite import median_composite
from forestwatch.preprocess.splits import (assign_block_splits, check_no_leakage, pixel_split_map,
                                           block_id_map, TRAIN, VAL, TEST, BUFFER)
from forestwatch.change.baseline import detect_change, remove_small_components
from forestwatch.eval.metrics import confusion, prf, polygon_metrics
from forestwatch.synthetic import make_scene_pair


def test_cloud_mask_flags_cloud_and_shadow():
    scl = np.full((20, 20), 4)
    scl[5:8, 5:8] = 9      # cloud
    scl[12, 12] = 3        # shadow
    v = valid_mask_from_scl(scl, dilate_px=0)
    assert not v[6, 6] and not v[12, 12] and v[0, 0]
    assert valid_mask_from_scl(scl, dilate_px=1)[4, 4] == False  # edge dilation


def test_ndvi_known_values():
    assert np.isclose(ndvi(np.array([0.5]), np.array([0.1]))[0], 0.4 / 0.6, atol=1e-6)
    assert np.isnan(ndvi(np.array([0.0]), np.array([0.0]))[0])


def test_reflectance_offset_after_baseline_change():
    dn = np.array([2000.0])
    assert np.isclose(scale_reflectance(dn, date(2021, 6, 1))[0], 0.2)
    assert np.isclose(scale_reflectance(dn, date(2023, 6, 1))[0], 0.1)


def test_composite_ignores_clouds_and_requires_min_obs():
    vals = np.stack([np.full((2, 2), 0.6), np.full((2, 2), 0.7), np.full((2, 2), 0.1)])
    valid = np.stack([np.ones((2, 2), bool), np.ones((2, 2), bool), np.zeros((2, 2), bool)])
    comp, ok = median_composite(vals, valid, min_obs=2)
    assert np.allclose(comp, 0.65) and ok.all()
    _, ok1 = median_composite(vals, valid, min_obs=3)
    assert not ok1.any()


def test_split_has_no_leakage_and_all_classes():
    for seed in range(10):
        g = assign_block_splits(8, 8, (0.6, 0.2, 0.2), seed=seed, buffer=1)
        assert check_no_leakage(g, 1)
        assert (g == TEST).any() and (g == VAL).any()


def test_split_is_deterministic_and_pixel_map_matches():
    g1 = assign_block_splits(6, 6, seed=3); g2 = assign_block_splits(6, 6, seed=3)
    assert np.array_equal(g1, g2)
    pm = pixel_split_map(600, 600, 100, g1)
    assert pm.shape == (600, 600) and pm[0, 0] == g1[0, 0] and pm[599, 599] == g1[5, 5]
    ids = block_id_map(600, 600, 100)
    assert ids[0, 0] == 0 and ids[599, 599] == 35


def test_small_components_removed():
    m = np.zeros((20, 20), bool); m[2:4, 2:4] = True; m[10:16, 10:16] = True
    out = remove_small_components(m, 10)
    assert not out[2, 2] and out[12, 12]


def test_detect_change_respects_cloud_and_forest_rules():
    before = np.full((30, 30), 0.7, "float32"); after = before.copy()
    after[5:15, 5:15] = 0.2                      # real clearing
    after[20:28, 20:28] = 0.2                    # cleared, but cloud-covered in 'after'
    vb = np.ones((30, 30), bool); va = vb.copy(); va[20:28, 20:28] = False
    out = detect_change(before, after, vb, va, 0.4, 0.25, 10)
    assert out[8, 8] and not out[24, 24]
    bare = np.full((30, 30), 0.1, "float32")     # was never vegetated
    assert not detect_change(bare, bare - 0.05, vb, vb, 0.4, 0.25, 10).any()


def test_metrics_hand_computed():
    pred = np.array([[1, 1, 0, 0]], bool); truth = np.array([[1, 0, 1, 0]], bool)
    c = confusion(pred, truth)
    assert c == {"tp": 1, "fp": 1, "fn": 1, "tn": 1}
    r = prf(c)
    assert np.isclose(r["precision"], 0.5) and np.isclose(r["f1"], 0.5) and np.isclose(r["iou"], 1 / 3)


def test_polygon_metrics_counts_patches():
    truth = np.zeros((20, 20), bool); truth[2:6, 2:6] = True; truth[12:16, 12:16] = True
    pred = np.zeros_like(truth); pred[2:6, 2:6] = True
    r = polygon_metrics(pred, truth)
    assert r["true_patches"] == 2 and r["detected"] == 1 and r["correct_blobs"] == 1


def test_seasonal_dip_creates_false_alarms_and_synthetic_is_deterministic():
    a = make_scene_pair(256, 256, seed=1, season_dip=0.0)
    b = make_scene_pair(256, 256, seed=1, season_dip=0.0)
    assert np.array_equal(a["ndvi_after"], b["ndvi_after"])
    def fp(d):
        p = detect_change(d["ndvi_before"], d["ndvi_after"], d["valid_before"], d["valid_after"])
        return confusion(p, d["truth"])["fp"]
    assert fp(make_scene_pair(256, 256, seed=1, season_dip=0.35)) > fp(a)


def test_rasterize_polygon_with_hole_and_outside_polygon():
    from forestwatch.labels.rasterize import rasterize_geojson
    tf = (10, 0, 500000, 0, -10, 3000000)              # 10 m pixels, north-up
    sq = [[500050, 2999950], [500150, 2999950], [500150, 2999850], [500050, 2999850], [500050, 2999950]]
    hole = [[500080, 2999920], [500100, 2999920], [500100, 2999900], [500080, 2999900], [500080, 2999920]]
    gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [sq, hole]}},
        {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 0]]]}}]}
    m, n = rasterize_geojson(gj, tf, (20, 20), "EPSG:32643", "EPSG:32643")
    assert n == 2 and m.sum() == 100 - 4               # 10x10 square minus 2x2 hole; outside polygon adds nothing
    assert m[5, 5] and not m[8, 8] and not m[0, 0]
