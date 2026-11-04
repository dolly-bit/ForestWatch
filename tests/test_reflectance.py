from datetime import date
import numpy as np
from forestwatch.preprocess.indices import scale_reflectance, scale_with_catalog, ndvi


def test_catalog_scaling_matches_the_declared_formula():
    dn = np.array([1300.0, 5000.0, 900.0])
    out = scale_with_catalog(dn, 0.0001, -0.1)
    assert np.allclose(out, [0.03, 0.4, 0.0], atol=1e-6)               # 900 DN -> -0.01 -> clipped to 0
    assert np.allclose(scale_with_catalog(dn, 0.0001, 0.0), [0.13, 0.5, 0.09], atol=1e-6)


def test_explicit_offset_overrides_the_date_rule():
    dn = np.array([1300.0])
    assert np.isclose(scale_reflectance(dn, date(2024, 1, 1))[0], 0.03)                  # date rule: -1000
    assert np.isclose(scale_reflectance(dn, date(2024, 1, 1), offset_dn=0.0)[0], 0.13)   # override: none
    assert np.isclose(scale_reflectance(dn, date(2021, 1, 1))[0], 0.13)                  # old data: none


def test_wrong_offset_saturates_ndvi_which_is_the_symptom_we_saw():
    red_dn, nir_dn = np.array([600.0]), np.array([3500.0])               # data WITHOUT the +1000 offset
    wrong_red = scale_reflectance(red_dn, date(2024, 1, 1))              # subtracting 1000 anyway -> clipped to 0
    wrong_nir = scale_reflectance(nir_dn, date(2024, 1, 1))
    assert wrong_red[0] == 0.0 and abs(ndvi(wrong_nir, wrong_red)[0] - 1.0) < 1e-6
    right = ndvi(scale_reflectance(nir_dn, date(2024, 1, 1), offset_dn=0.0), scale_reflectance(red_dn, date(2024, 1, 1), offset_dn=0.0))
    assert 0.7 < right[0] < 0.8


def test_scaling_modes_and_precedence():
    from forestwatch.data.download import _reflectance
    dn, acq = np.array([1300.0]), date(2024, 1, 1)
    scene = {"raster": {"red": {"scale": 0.0001, "offset": -0.1}}}
    auto, how = _reflectance(dn, "red", scene, {}, acq)
    assert np.isclose(auto[0], 0.03) and "catalog" in how                                  # catalog wins in auto mode
    none, how = _reflectance(dn, "red", scene, {"reflectance": {"mode": "none"}}, acq)
    assert np.isclose(none[0], 0.13) and "no offset" in how                                # mode none ignores the catalog
    old, how = _reflectance(dn, "red", scene, {"reflectance": {"mode": "date_rule"}}, acq)
    assert np.isclose(old[0], 0.03) and "date_rule" in how
    fb, how = _reflectance(dn, "nir", {}, {}, acq)                                          # nothing declared: date rule
    assert np.isclose(fb[0], 0.03) and "date rule" in how
    ov, how = _reflectance(dn, "nir", {}, {"reflectance": {"boa_add_offset": 0}}, acq)
    assert np.isclose(ov[0], 0.13) and "config" in how
    try:
        _reflectance(dn, "red", {}, {"reflectance": {"mode": "bogus"}}, acq); assert False
    except ValueError:
        pass


def _fake_build(red_dn, nir_dn, mode, scene_raster):
    """Run build_scene_stack with the network/raster reads replaced by arrays."""
    import tempfile
    import forestwatch.data.download as dl
    from forestwatch.data.stack_io import load_stack
    arrays = {"red": red_dn, "nir": nir_dn, "swir22": red_dn, "scl": np.full(red_dn.shape, 4)}
    saved = dl.read_band, dl.make_target_grid
    dl.read_band = lambda href, crs, tf, w, h, categorical=False: arrays[href]
    dl.make_target_grid = lambda bbox, crs, res: ((10.0, 0.0, 500000.0, 0.0, -10.0, 3000000.0), red_dn.shape[1], red_dn.shape[0])
    try:
        scene = {"id": "S", "datetime": "2022-11-20T05:00:00Z", "assets": {k: k for k in arrays}, "raster": scene_raster}
        cfg = {"region": {"crs": "EPSG:32643", "bbox": [0, 0, 1, 1], "resolution_m": 10},
               "cloud_mask": {"valid_scl_classes": [4, 5, 6, 7]}, "reflectance": {"mode": mode}}
        with tempfile.TemporaryDirectory() as tmp:
            path, meta = dl.build_scene_stack(scene, cfg, tmp)
            return load_stack(path)[0], meta
    finally:
        dl.read_band, dl.make_target_grid = saved


def test_auto_rejects_a_declared_offset_that_the_pixels_contradict():
    rng = np.random.default_rng(0)
    red = rng.normal(500, 150, (40, 40)).clip(100, None).astype("float32")      # DN WITHOUT the +1000 offset
    nir = rng.normal(2800, 300, (40, 40)).astype("float32")
    declared = {b: {"scale": 0.0001, "offset": -0.1} for b in ("red", "nir", "swir22")}
    arr, meta = _fake_build(red, nir, "auto", declared)
    assert "REJECTED" in meta["reflectance_scaling"] and meta["red_zero_fraction"] < 0.05
    assert 0.03 < np.median(arr["red"]) < 0.07 and 0.25 < np.median(arr["nir"]) < 0.31
    flawed, fmeta = _fake_build(red, nir, "date_rule", declared)               # the old behaviour is still available, and flagged
    assert fmeta["red_zero_fraction"] > 0.9 and np.median(flawed["red"]) == 0.0


def test_auto_keeps_a_declared_offset_when_the_pixels_agree():
    rng = np.random.default_rng(1)
    red = rng.normal(1500, 150, (40, 40)).astype("float32")                    # DN WITH the +1000 offset
    nir = rng.normal(3800, 300, (40, 40)).astype("float32")
    declared = {b: {"scale": 0.0001, "offset": -0.1} for b in ("red", "nir", "swir22")}
    arr, meta = _fake_build(red, nir, "auto", declared)
    assert "REJECTED" not in meta["reflectance_scaling"] and "catalog" in meta["reflectance_scaling"]
    assert 0.04 < np.median(arr["red"]) < 0.06 and meta["red_zero_fraction"] < 0.01
