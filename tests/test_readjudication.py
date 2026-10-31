import csv
import sys
import tempfile
from pathlib import Path
import numpy as np
import pytest

from forestwatch.readjudication import (make_blank_sheet, write_csv, validate_sheet, merge, BLANK_COLUMNS,
                                        CHANGE_TYPES)
from forestwatch.landcover_diag import landcover_for_rows, ndvi_by_class, CLASS_NAMES
from forestwatch.review_summary import summarize
from test_exclusions import _stub_pyproj, TRANSFORM, CRS

ORIG = [{"id": str(i), "area_ha": "0.5", "mean_ndvi_drop": "0.4", "kept_by_seasonal": "yes",
         "lat": "28.005", "lon": str(77.0 + (10 + 10 * i) * 1e-4), "maps_link": "x", "page": "1",
         "verdict": "y"} for i in range(1, 7)]


def test_blank_sheet_is_blind_shuffled_and_deterministic():
    a, b = make_blank_sheet(ORIG, seed=1), make_blank_sheet(ORIG, seed=1)
    assert a == b and sorted(r["id"] for r in a) == [str(i) for i in range(1, 7)]
    assert [r["id"] for r in a] != [str(i) for i in range(1, 7)]               # shuffled
    for r in a:
        assert not ({"verdict", "mean_ndvi_drop", "kept_by_seasonal", "page"} & set(r))
        assert r["change_type"] == "" and r["verdict_v2"] == ""
    assert set(BLANK_COLUMNS) == set(a[0])


def test_sheet_is_never_overwritten():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "s.csv"
        write_csv(p, make_blank_sheet(ORIG), BLANK_COLUMNS)
        before = p.read_text()
        with pytest.raises(FileExistsError):
            write_csv(p, make_blank_sheet(ORIG), BLANK_COLUMNS)
        assert p.read_text() == before


def test_validation_flags_bad_values_and_inconsistency():
    rows = [{"id": "1", "change_type": "natural_vegetation_loss", "verdict_v2": "y"},
            {"id": "2", "change_type": "crop_cycle_or_field_change", "verdict_v2": "y"},   # inconsistent
            {"id": "3", "change_type": "forest", "verdict_v2": "n"},                      # invalid type
            {"id": "4", "change_type": "cannot_tell", "verdict_v2": "zz"},                # invalid verdict
            {"id": "5", "change_type": "", "verdict_v2": ""}]                             # not filled
    v = validate_sheet(rows)
    assert v["n_unfilled"] == 1 and v["inconsistent"] == [("2", "crop_cycle_or_field_change", "y")]
    assert v["bad_types"] == [("3", "forest")] and v["bad_verdicts"] == [("4", "zz")]
    ok_rows = [{"id": str(k), "change_type": c, "verdict_v2": "y" if c in (
        "natural_vegetation_loss", "construction_or_road", "mining_or_quarry", "other_bare_ground") else
        ("?" if c == "cannot_tell" else "n")} for k, c in enumerate(CHANGE_TYPES)]
    assert validate_sheet(ok_rows)["warnings"] == []


def test_landcover_lookup_merge_and_summary_by_class():
    saved = sys.modules.get("pyproj"); sys.modules["pyproj"] = _stub_pyproj()
    try:
        grid = np.full((100, 100), 40, "uint8"); grid[:, :45] = 10          # cols 0-44 tree cover, rest cropland
        classes = landcover_for_rows(ORIG, grid, TRANSFORM, CRS)           # cols 20,30,40,50,60,70
        assert classes == [10, 10, 10, 40, 40, 40]
        sheet = make_blank_sheet(ORIG)
        for r in sheet:
            i = int(r["id"])
            r["change_type"], r["verdict_v2"] = (("natural_vegetation_loss", "y") if i <= 2 else
                                                 ("crop_cycle_or_field_change", "n"))
        merged, cols = merge(ORIG, sheet, classes, CLASS_NAMES)
        assert cols[:9] == list(ORIG[0].keys()) and "landcover_name" in cols and "verdict_v2" in cols
        assert all(m["verdict"] == "y" for m in merged)                  # original verdicts untouched
        assert [m["landcover_name"] for m in merged][:4] == ["tree cover"] * 3 + ["cropland"]
        rows = [{**m, "verdict": m["verdict_v2"]} for m in merged]
        s = summarize(rows, cols + ["verdict"] if "verdict" not in cols else cols, group_by="landcover_name")
        g = s["by_group"]["groups"]
        assert g["tree cover"]["y"] == 2 and g["tree cover"]["n"] == 1 and g["cropland"]["y"] == 0
    finally:
        if saved is None:
            sys.modules.pop("pyproj", None)
        else:
            sys.modules["pyproj"] = saved


def test_ndvi_by_class_uses_no_labels_and_reports_detector_bias():
    ndvi = np.full((10, 10), 0.2, "float32"); ndvi[:, 5:] = 0.7            # right half green (like irrigated crops)
    grid = np.full((10, 10), 20, "uint8"); grid[:, 5:] = 40               # left shrubland, right cropland
    valid = np.ones((10, 10), bool)
    mask = np.zeros((10, 10), bool); mask[2:4, 6:8] = True               # detector fires only in the green half
    rows = {r["name"]: r for r in ndvi_by_class(ndvi, valid, mask, grid, 0.4)}
    assert rows["shrubland"]["share_ndvi_at_least_threshold"] == 0.0 and rows["shrubland"]["flagged_share_of_class"] == 0.0
    assert rows["cropland"]["share_ndvi_at_least_threshold"] == 1.0 and rows["cropland"]["share_of_all_detections"] == 1.0
    assert abs(rows["cropland"]["flagged_share_of_class"] - 4 / 50) < 1e-9
    assert abs(rows["cropland"]["median_ndvi_before"] - 0.7) < 1e-6


def test_compare_passes_known_table_and_kappa():
    from forestwatch.readjudication import compare_passes
    pairs = [("y", "y")] * 3 + [("y", "n")] * 2 + [("n", "y")] * 1 + [("n", "n")] * 4 + [("y", "?"), ("", "n")]
    rows = [{"id": str(i), "verdict": a, "verdict_v2": b, "change_type": "crop_cycle_or_field_change",
             "landcover_name": "cropland"} for i, (a, b) in enumerate(pairs)]
    r = compare_passes(rows)
    assert r["n_both_decided"] == 10 and r["skipped_unsure_or_blank"] == 2
    assert r["table"] == {"first_y_second_y": 3, "first_y_second_n": 2, "first_n_second_y": 1, "first_n_second_n": 4}
    assert abs(r["agreement"] - 0.7) < 1e-12 and abs(r["kappa"] - 0.4) < 1e-12
    assert len(r["disagreements"]) == 3
    assert compare_passes([])["agreement"] is None
    perfect = compare_passes([{"id": "1", "verdict": "y", "verdict_v2": "y"}, {"id": "2", "verdict": "y", "verdict_v2": "y"}])
    assert perfect["kappa"] is None                               # everyone same label: kappa undefined, no crash
