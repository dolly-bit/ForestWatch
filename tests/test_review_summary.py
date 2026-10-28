import csv
import tempfile
from pathlib import Path
import pytest

from forestwatch.review_summary import (ReviewInputError, read_review_csv, validate, summarize, render_markdown,
                                        dumps_json, init_annotations, classify_verdict, REQUIRED_COLUMNS)

COLS = ["id", "area_ha", "mean_ndvi_drop", "kept_by_seasonal", "lat", "lon", "maps_link", "page", "verdict"]


def row(i, verdict, kept="yes", **kw):
    r = {"id": str(i), "area_ha": "0.5", "mean_ndvi_drop": "0.4", "kept_by_seasonal": kept, "lat": "28.3",
         "lon": "77.2", "maps_link": "x", "page": "1", "verdict": verdict}
    r.update(kw)
    return r


def write_csv(path, rows, cols=COLS):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows)


FIXTURE = [row(1, "y"), row(2, "y", kept="no"), row(3, "y"), row(4, "n"), row(5, "?"), row(6, "")]


def test_known_fixture_counts_and_rate():
    s = summarize(FIXTURE, COLS)
    o = s["overall"]
    assert (o["y"], o["n"], o["unsure"], o["unreviewed"], o["decided"]) == (3, 1, 1, 1, 4)
    assert o["positive_rate_among_decided"] == 0.75
    assert abs(o["ci95_wilson"][0] - 0.3006) < 0.002 and abs(o["ci95_wilson"][1] - 0.9544) < 0.002
    assert o["sensitivity_to_unsure"] == {"all_unsure_negative": 0.6, "all_unsure_positive": 0.8}
    g = s["by_group"]["groups"]
    assert g["yes"]["y"] == 2 and g["no"]["y"] == 1 and g["no"]["decided"] == 1


def test_valid_input_has_no_warnings_or_errors():
    v = validate([row(1, "y"), row(2, "n")], COLS)
    assert v["errors"] == [] and v["warnings"] == [] and v["unique_ids"] == 2


def test_missing_required_column_is_an_error():
    cols = [c for c in COLS if c != "verdict"]
    s = summarize([{k: v for k, v in row(1, "y").items() if k != "verdict"}], cols)
    assert s["overall"] is None and "verdict" in s["validation"]["errors"][0]
    assert "ERRORS" in render_markdown(s)


def test_invalid_and_noncanonical_verdicts_are_reported_not_hidden():
    s = summarize([row(1, "yes"), row(2, "zzz"), row(3, "n"), row(4, "Y "), row(5, "maybe")], COLS)
    v, o = s["validation"], s["overall"]
    assert [i["value"] for i in v["invalid_verdicts"]] == ["zzz"] and o["invalid"] == 1
    assert o["y"] == 2 and o["n"] == 1 and o["decided"] == 3 and o["unsure"] == 1   # 'yes','Y ' -> y; 'maybe' -> ?
    assert any("normalised" in w for w in v["warnings"]) and any("unrecognised" in w for w in v["warnings"])


def test_duplicate_ids_counted_once_and_reported():
    s = summarize([row(1, "y"), row(1, "n"), row(2, "n")], COLS)
    assert s["validation"]["duplicate_ids"] == ["1"] and s["overall"]["rows"] == 2 and s["overall"]["y"] == 1
    assert any("Duplicate" in w for w in s["validation"]["warnings"])


def test_missing_and_nonnumeric_values_are_warned():
    s = summarize([row(1, "y", area_ha=""), row(2, "n", lat="abc")], COLS)
    w = " ".join(s["validation"]["warnings"])
    assert "empty 'area_ha'" in w and "'lat'" in w and s["overall"]["rows"] == 2


def test_empty_inputs():
    assert "No data rows" in summarize([], COLS)["validation"]["errors"][0]
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "empty.csv"; p.write_text("")
        rows, cols = read_review_csv(p)
        assert rows == [] and cols == [] and summarize(rows, cols)["overall"] is None
        with pytest.raises(ReviewInputError):
            read_review_csv(Path(tmp) / "nope.csv")


def test_all_uncertain_and_zero_decided_give_undefined_rate_without_crashing():
    s = summarize([row(1, "?"), row(2, "?")], COLS, population_size=500)
    o = s["overall"]
    assert o["decided"] == 0 and o["positive_rate_among_decided"] is None and o["ci95_wilson"] is None
    assert o["rate_among_all_reviewed_with_unsure_as_not_positive"] == 0.0
    assert s["population_estimate"] is None
    assert "undefined" in render_markdown(s)
    z = summarize([row(1, ""), row(2, "")], COLS)["overall"]
    assert z["decided"] == 0 and z["sensitivity_to_unsure"] is None


def test_population_estimate_and_sampling_section():
    rows = [row(i, "y") for i in range(30)] + [row(100 + i, "n") for i in range(10)]
    meta = {"total_candidates": 1200, "eligible": 1000, "min_area_ha": 0.3, "sampled": 40, "seed": 0}
    s = summarize(rows, COLS, meta)
    pe = s["population_estimate"]
    assert pe["population_size"] == 1000 and abs(pe["expected_positive_candidates"] - 750) < 1e-9
    assert pe["expected_positive_candidates_ci95"][0] < 750 < pe["expected_positive_candidates_ci95"][1]
    md = render_markdown(s)
    assert "seed 0" in md and "not stratified" in md and "Not available from this file" in md


def test_report_generation_is_stable_and_states_limits():
    a, b = summarize(FIXTURE, COLS, input_path="p", input_sha256="h"), summarize(FIXTURE, COLS, input_path="p", input_sha256="h")
    assert render_markdown(a) == render_markdown(b) and dumps_json(a) == dumps_json(b)
    assert "not validated pixel-level precision or recall" in render_markdown(a)


def test_classify_and_annotation_template_never_overwrites():
    assert [classify_verdict(v) for v in ("y", "No", "?", " ", None, "zzz")] == ["y", "n", "?", "unreviewed", "unreviewed", "invalid"]
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "ann.csv"
        assert init_annotations(FIXTURE, p) == 6
        first = p.read_text()
        with pytest.raises(FileExistsError):
            init_annotations(FIXTURE, p)
        assert p.read_text() == first and first.splitlines()[0].startswith("candidate_id,reviewer")
