import copy
import numpy as np
import pytest
import xml.etree.ElementTree as ET

from forestwatch.eval.grids import GridMismatchError
from forestwatch.reference.rasterize import rasterize_chip_labels, check_same_grid, LOSS, NO_LOSS, EXCLUDED
from forestwatch.reference.export import to_kml, chip_center, labels_geojson, maps_link
from forestwatch.reference.qa import cohen_kappa, compare_reference_passes, rereview_ids
from forestwatch.reference.summary import summarize_labels, render_summary_md
from forestwatch.reference.sampling import sample_split
from test_reference_validation import _labels
from _phase2_helpers import META, SHAPE, WithPyproj, CRS, make_frame


def _chip(r0, c0, cls, uid):
    return {"unit_id": uid, "chip_row0": r0, "chip_row1": r0 + 32, "chip_col0": c0, "chip_col1": c0 + 32, "class_label": cls}


def test_rasterization_encoding_and_exclusions():
    rows = [_chip(0, 0, "loss", "a"), _chip(0, 32, "no_loss", "b"), _chip(32, 0, "uncertain", "c"), _chip(32, 32, "ignore", "d")]
    iv = np.ones(SHAPE, bool); iv[0:16, 32:64] = False                      # half of chip b has no clear imagery
    label, valid, index = rasterize_chip_labels(rows, SHAPE, 32, iv)
    assert label.dtype == np.uint8 and valid.dtype == np.uint8 and index.dtype == np.int32
    assert (label[:32, :32] == LOSS).all() and (label[:32, 32:64] == NO_LOSS).all()
    assert (label[32:64, :32] == EXCLUDED).all() and (label[32:64, 32:64] == EXCLUDED).all()     # uncertain/ignore never become no_loss
    assert valid[:32, :32].all() and not valid[32:64, :64].any() and not valid[0:16, 32:64].any() and valid[16:32, 32:64].all()
    assert (label[64:, :] == EXCLUDED).all() and not valid[64:, :].any() and not index[64:, :].any()
    assert index[0, 0] == 1 and index[0, 32] == 2 and index[32, 0] == 8 + 1       # (row_chip * n_cols + col_chip) + 1, n_cols = 8
    assert set(np.unique(label)) == {0, 1, 255}


def test_rasterization_rejects_overlaps_outside_chips_and_misaligned_grids():
    with pytest.raises(ValueError):
        rasterize_chip_labels([_chip(0, 0, "loss", "a"), _chip(0, 0, "no_loss", "b")], SHAPE, 32)
    with pytest.raises(ValueError):
        rasterize_chip_labels([_chip(240, 0, "loss", "a")], SHAPE, 32)
    with pytest.raises(GridMismatchError):
        rasterize_chip_labels([], SHAPE, 32, np.ones((10, 10), bool))
    check_same_grid(META, dict(META))
    for k, v in (("crs", "EPSG:4326"), ("width", 300), ("transform", [10, 0, 500005, 0, -10, 3000000])):
        with pytest.raises(GridMismatchError):
            check_same_grid(META, {**META, k: v})


def test_kml_geojson_and_links_carry_no_model_information():
    rows, _ = make_frame()
    chosen = sample_split(rows, "validation", 2, 2026)
    with WithPyproj():
        kml = to_kml(chosen, tuple(META["transform"]), CRS, "t")
        lat, lon = chip_center(chosen[0], tuple(META["transform"]), CRS)
        gj = labels_geojson([dict(c, class_label="loss") for c in chosen], tuple(META["transform"]), CRS, ["unit_id", "class_label"])
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    marks = ET.fromstring(kml).findall(".//k:Placemark", ns)
    assert len(marks) == len(chosen)
    assert "flagged" not in kml and "unflagged" not in kml and "stratum" not in kml and "natural" not in kml
    coords = marks[0].find(".//k:coordinates", ns).text.split()
    assert len(coords) == 5 and coords[0] == coords[-1]
    assert maps_link(lat, lon).startswith("https://www.google.com/maps?q=") and f"{lat}" in maps_link(lat, lon)
    assert gj["features"][0]["properties"] == {"unit_id": chosen[0]["unit_id"], "class_label": "loss"}


def test_kappa_agreement_and_rereview_subset():
    assert abs(cohen_kappa(list("yyynnnnnnn"), list("yynnnnnnny")) - cohen_kappa(list("yyynnnnnnn"), list("yynnnnnnny"))) < 1e-12
    a = ["loss"] * 5 + ["no_loss"] * 5
    b = ["loss"] * 3 + ["no_loss"] * 2 + ["loss"] * 1 + ["no_loss"] * 4
    assert abs(cohen_kappa(a, b) - 0.4) < 1e-12
    assert cohen_kappa(["a", "a"], ["a", "a"]) is None and cohen_kappa([], []) is None
    first = [{"unit_id": str(i), "class_label": c} for i, c in enumerate(a)]
    second = [{"unit_id": str(i), "class_label": c} for i, c in enumerate(b)] + [{"unit_id": "x", "class_label": "loss"}]
    r = compare_reference_passes(first, second)
    assert r["n_compared"] == 10 and abs(r["agreement"] - 0.7) < 1e-12 and len(r["disagreements"]) == 3
    ids = rereview_ids(first, 0.3, 5)
    assert ids == rereview_ids(first, 0.3, 5) and len(ids) == 3 and set(ids) <= {r["unit_id"] for r in first}


def test_summary_counts_areas_and_estimates():
    labels, _, chosen = _labels(6)
    s = summarize_labels(labels, chosen, 10.24)
    assert s["n_labels"] == 6 and sum(v["chips"] for c in s["by_split"].values() for v in c.values()) == 6
    cell = next(iter(s["by_split"]["validation"].values()))
    assert abs(cell["area_ha"] - cell["chips"] * 10.24) < 1e-9
    assert s["provenance_gaps"]["missing_evidence_source"] == 0 and s["provenance_gaps"]["evidence_date_unknown"] == 6
    assert "validation" in s["estimates"] and "unit-level" in render_summary_md(s)
    assert "missing at random" in s["note"]
