from datetime import date

import numpy as np
import pytest

from forestwatch.preprocess.indices import scale_reflectance, scale_with_catalog, ndvi


def test_catalog_scaling_matches_the_declared_formula():
    dn = np.array([1300.0, 5000.0, 900.0])
    out = scale_with_catalog(dn, 0.0001, -0.1)
    assert np.allclose(out, [0.03, 0.4, 0.0], atol=1e-6)
    assert np.allclose(scale_with_catalog(dn, 0.0001, 0.0), [0.13, 0.5, 0.09], atol=1e-6)


def test_explicit_offset_overrides_the_date_rule():
    dn = np.array([1300.0])
    assert np.isclose(scale_reflectance(dn, date(2024, 1, 1))[0], 0.03)
    assert np.isclose(scale_reflectance(dn, date(2024, 1, 1), offset_dn=0.0)[0], 0.13)
    assert np.isclose(scale_reflectance(dn, date(2021, 1, 1))[0], 0.13)


def test_wrong_offset_saturates_ndvi_which_is_the_symptom_we_saw():
    red_dn, nir_dn = np.array([600.0]), np.array([3500.0])
    wrong_red = scale_reflectance(red_dn, date(2024, 1, 1))
    wrong_nir = scale_reflectance(nir_dn, date(2024, 1, 1))
    assert wrong_red[0] == 0.0 and abs(ndvi(wrong_nir, wrong_red)[0] - 1.0) < 1e-6
    right = ndvi(
        scale_reflectance(nir_dn, date(2024, 1, 1), offset_dn=0.0),
        scale_reflectance(red_dn, date(2024, 1, 1), offset_dn=0.0),
    )
    assert 0.7 < right[0] < 0.8


def test_auto_flag_true_means_offset_is_already_applied():
    from forestwatch.data.download import _reflectance

    dn = np.array([1300.0, 5000.0])
    scene = {
        "raster": {"red": {"scale": 0.0001, "offset": -0.1}},
        "stac_properties": {"earthsearch:boa_offset_applied": True},
    }
    result, decision = _reflectance(dn, "red", scene, {}, date(2024, 1, 1))
    assert np.allclose(result, [0.13, 0.5])
    assert "offset=0" in decision


def test_auto_flag_false_applies_catalog_offset():
    from forestwatch.data.download import _reflectance

    dn = np.array([1300.0, 5000.0])
    scene = {
        "raster": {"red": {"scale": 0.0001, "offset": -0.1}},
        "stac_properties": {"earthsearch:boa_offset_applied": False},
    }
    result, decision = _reflectance(dn, "red", scene, {}, date(2024, 1, 1))
    assert np.allclose(result, [0.03, 0.4])
    assert "offset=-0.1" in decision


def test_auto_uses_catalog_when_earth_search_flag_is_missing():
    from forestwatch.data.download import _reflectance

    dn = np.array([1300.0])
    scene = {"raster": {"red": {"scale": 0.0001, "offset": -0.1}}}
    result, decision = _reflectance(dn, "red", scene, {}, date(2024, 1, 1))
    assert np.isclose(result[0], 0.03)
    assert "flag unavailable" in decision


def test_scaling_modes_and_config_override():
    from forestwatch.data.download import _reflectance

    dn, acquisition = np.array([1300.0]), date(2024, 1, 1)
    scene = {"raster": {"red": {"scale": 0.0001, "offset": -0.1}}}
    auto, decision = _reflectance(dn, "red", scene, {}, acquisition)
    assert np.isclose(auto[0], 0.03) and "catalog" in decision

    no_offset, decision = _reflectance(dn, "red", scene, {"reflectance": {"mode": "none"}}, acquisition)
    assert np.isclose(no_offset[0], 0.13) and "no additional offset" in decision

    legacy, decision = _reflectance(dn, "red", scene, {"reflectance": {"mode": "date_rule"}}, acquisition)
    assert np.isclose(legacy[0], 0.03) and "date_rule" in decision

    fallback, decision = _reflectance(dn, "nir", {}, {}, acquisition)
    assert np.isclose(fallback[0], 0.03) and "fallback" in decision

    explicit, decision = _reflectance(
        dn, "nir", {}, {"reflectance": {"boa_add_offset": 0}}, acquisition
    )
    assert np.isclose(explicit[0], 0.13) and "config" in decision

    with pytest.raises(ValueError, match="unknown reflectance mode"):
        _reflectance(dn, "red", {}, {"reflectance": {"mode": "bogus"}}, acquisition)


def _fake_build(red_dn, nir_dn, mode, scene_raster, stac_properties=None, reflectance_extra=None):
    import tempfile

    import forestwatch.data.download as dl
    from forestwatch.data.stack_io import load_stack

    arrays = {
        "red": red_dn,
        "nir": nir_dn,
        "swir22": red_dn,
        "scl": np.full(red_dn.shape, 4),
    }
    saved = dl.read_band, dl.make_target_grid
    dl.read_band = lambda href, crs, tf, w, h, categorical=False: arrays[href]
    dl.make_target_grid = lambda bbox, crs, res: (
        (10.0, 0.0, 500000.0, 0.0, -10.0, 3000000.0),
        red_dn.shape[1],
        red_dn.shape[0],
    )
    try:
        scene = {
            "id": "S",
            "datetime": "2022-11-20T05:00:00Z",
            "assets": {key: key for key in arrays},
            "raster": scene_raster,
            "stac_properties": stac_properties or {},
        }
        reflectance = {"mode": mode, **(reflectance_extra or {})}
        cfg = {
            "region": {"crs": "EPSG:32643", "bbox": [0, 0, 1, 1], "resolution_m": 10},
            "cloud_mask": {"valid_scl_classes": [4, 5, 6, 7]},
            "reflectance": reflectance,
        }
        with tempfile.TemporaryDirectory() as tmp:
            path, meta = dl.build_scene_stack(scene, cfg, tmp)
            arrays_out, _ = load_stack(path)
            return arrays_out, meta
    finally:
        dl.read_band, dl.make_target_grid = saved


def test_build_scene_stack_fails_closed_on_conflicting_metadata():
    red = np.full((10, 10), 800, dtype="float32")
    nir = np.full((10, 10), 2500, dtype="float32")
    declared = {band: {"scale": 0.0001, "offset": -0.1} for band in ("red", "nir", "swir22")}
    properties = {
        "s2:processing_baseline": "04.00",
        "earthsearch:boa_offset_applied": False,
    }
    with pytest.raises(ValueError, match="metadata conflict"):
        _fake_build(red, nir, "auto", declared, properties)


def test_build_scene_stack_records_scaling_and_stac_provenance_when_explicitly_overridden():
    red = np.full((10, 10), 800, dtype="float32")
    nir = np.full((10, 10), 2500, dtype="float32")
    declared = {band: {"scale": 0.0001, "offset": -0.1} for band in ("red", "nir", "swir22")}
    properties = {
        "s2:processing_baseline": "04.00",
        "earthsearch:boa_offset_applied": False,
    }
    arrays, meta = _fake_build(red, nir, "none", declared, properties)
    assert np.isclose(np.median(arrays["red"]), 0.08)
    assert "mode none" in meta["reflectance_scaling"]["red"]
    assert meta["stac_properties"] == properties
    assert meta["reflectance_metadata_conflict"] is False
