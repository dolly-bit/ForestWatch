import copy
import pytest

from forestwatch.reference.blocks import prepare_blocks
from forestwatch.reference.labels import make_label_sheet, merge_labels, validate_labels, SHEET_COLUMNS
from forestwatch.reference.sampling import sample_split
from forestwatch.reference.schema import guard_test_labels, LABEL_COLUMNS, SHEET_COLUMNS as SC
from _phase2_helpers import make_frame, SHAPE, META, ref_cfg, WithPyproj, CRS


def _labels(n=6):
    rows, manifest = make_frame()
    chosen = sample_split(rows, "validation", 2, 2026)[:n]
    sheet = [{"unit_id": r["unit_id"], "class_label": "no_loss" if i % 2 else "loss", "loss_type": "" if i % 2 else "natural_to_built",
              "confidence": "high", "evidence_source": "Google Earth imagery", "evidence_before_date": "2022-11-01",
              "evidence_after_date": "unknown", "event_start": "", "event_end": "", "reviewer_id": "R1",
              "review_date": "2026-11-02", "notes": ""} for i, r in enumerate(chosen)]
    labels, unl = merge_labels(sheet, chosen, ref_cfg(), "2026-11-03", CRS)
    return labels, prepare_blocks(manifest, 10.0, SHAPE), chosen


def _validate(rows, blocks):
    return validate_labels(rows, blocks, SHAPE, 32, 64, ref_cfg())


def test_valid_labels_pass_and_all_columns_exist():
    labels, blocks, _ = _labels()
    assert labels and set(LABEL_COLUMNS) <= set(labels[0])
    res = _validate(labels, blocks)
    assert res["errors"] == [], res["errors"]


def test_blind_sheet_hides_everything_about_the_model_and_sampling():
    _, _, chosen = _labels()
    with WithPyproj():
        sheet = make_label_sheet(chosen, tuple(META["transform"]), CRS, "R1")
    assert set(sheet[0]) == set(SC) and len(sheet) == len(chosen)
    forbidden = {"stratum", "baseline_status", "selection_probability", "split", "block_id", "landcover_group", "flagged_px"}
    assert not forbidden & set(sheet[0])
    assert all(r["class_label"] == "" and r["reviewer_id"] == "R1" and "google.com/maps" in r["maps_link"] for r in sheet)
    with WithPyproj():
        assert [r["unit_id"] for r in sheet] != [r["unit_id"] for r in sorted(sheet, key=lambda r: r["unit_id"])] or len(sheet) < 3


def test_merge_reports_unlabelled_and_rejects_unknown_units():
    _, _, chosen = _labels()
    sheet = [{"unit_id": chosen[0]["unit_id"], "class_label": ""}]
    labels, unl = merge_labels(sheet, chosen, ref_cfg(), "2026-11-03", CRS)
    assert labels == [] and unl == [chosen[0]["unit_id"]]
    with pytest.raises(ValueError):
        merge_labels([{"unit_id": "nope", "class_label": "loss"}], chosen, ref_cfg(), "2026-11-03", CRS)


@pytest.mark.parametrize("field,value,fragment", [
    ("class_label", "no_changes", "class_label"),
    ("confidence", "certain", "confidence"),
    ("evidence_source", "", "evidence_source"),
    ("review_date", "03/11/2026", "review_date"),
    ("evidence_before_date", "2022-13", "evidence_before_date"),
    ("evidence_after_date", "last year", "evidence_after_date"),
    ("reviewer_id", "", "reviewer_id"),
    ("loss_type", "forest_fire", "loss_type"),
    ("chip_row1", "999", "outside the study grid"),
    ("chip_row1", "+16", "aligned"),
    ("split", "test", "frozen manifest"),
    ("block_id", "999", "block_id"),
    ("selection_probability", "1.5", "selection_probability"),
])
def test_validation_catches_each_problem(field, value, fragment):
    labels, blocks, _ = _labels()
    bad = copy.deepcopy(labels)
    bad[0][field] = str(int(bad[0]["chip_row0"]) + 16) if value == "+16" else value
    res = _validate(bad, blocks)
    text = " ".join(res["errors"] + res["warnings"])
    assert fragment in text, (field, text)


def test_validation_catches_duplicates_overlaps_and_reversed_events():
    labels, blocks, _ = _labels()
    dup = labels + [dict(labels[0])]
    assert any("duplicate" in e for e in _validate(dup, blocks)["errors"])
    twin = dict(labels[0], label_id="L-other", unit_id="C999_999", class_label="no_loss")      # same area, other class
    assert any("overlaps" in e for e in _validate(labels + [twin], blocks)["errors"])
    rev = copy.deepcopy(labels); rev[0]["event_start"], rev[0]["event_end"] = "2024-05-01", "2023-01-01"
    assert any("after event_end" in e for e in _validate(rev, blocks)["errors"])
    assert _validate([], blocks)["errors"]


def test_uncertain_stays_uncertain_and_buffer_chips_cannot_be_labelled():
    labels, blocks, _ = _labels()
    unc = copy.deepcopy(labels); unc[0]["class_label"] = "uncertain"; unc[0]["loss_type"] = ""
    assert _validate(unc, blocks)["errors"] == []
    assert _validate(unc, blocks)["counts"]["by_class"]["uncertain"] == 1
    buf = [b for b in blocks if b["split"] == "buffer"][0]
    bad = copy.deepcopy(labels); bad[0].update(chip_row0=buf["px_row0"], chip_row1=buf["px_row0"] + 32, chip_col0=buf["px_col0"],
                                               chip_col1=buf["px_col0"] + 32, block_id=buf["block_id"], split="buffer")
    assert any("buffer" in e for e in _validate(bad, blocks)["errors"])


def test_test_labels_are_guarded():
    assert guard_test_labels(["train", "validation"]) == ["train", "validation"]
    with pytest.raises(PermissionError):
        guard_test_labels(["validation", "test"])
    assert guard_test_labels(["test"], allow_test=True) == ["test"]


def test_imagery_dates_may_be_partial_or_unknown():
    labels, blocks, _ = _labels()
    for v in ("2024", "2023-07", "2023-07-15", "unknown", "Unknown"):
        ok = copy.deepcopy(labels); ok[0]["evidence_after_date"] = v
        assert _validate(ok, blocks)["errors"] == [], v
    for v in ("", "2023-7", "2023-02-31", "99"):
        bad = copy.deepcopy(labels); bad[0]["evidence_after_date"] = v
        assert any("evidence_after_date" in e for e in _validate(bad, blocks)["errors"]), v
