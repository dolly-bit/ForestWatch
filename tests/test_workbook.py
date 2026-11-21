import tempfile
from pathlib import Path
import pytest

from forestwatch.reference.workbook import (build_workbook, read_workbook, check_answers, apply_to_sheet, COLUMNS, FILL_COLUMNS)
from forestwatch.reference.schema import SHEET_COLUMNS
from _phase2_helpers import ref_cfg


def _sheet(n=5):
    return [{**{c: "" for c in SHEET_COLUMNS}, "unit_id": f"C{i:03d}_000", "lat": "28.3", "lon": "77.2",
             "maps_link": f"https://www.google.com/maps?q=28.3,77.{i}&t=k&z=17", "reviewer_id": "R1"} for i in range(n)]


def _fill(path, answers):
    from openpyxl import load_workbook
    wb = load_workbook(path)
    ws = wb["Label"]
    head = {c.value: j + 1 for j, c in enumerate(ws[1])}
    for i, ans in enumerate(answers, start=2):
        for k, v in ans.items():
            ws.cell(row=i, column=head[k], value=v)
    wb.save(path)


def test_workbook_has_dropdowns_text_dates_links_and_a_guide():
    pytest.importorskip("openpyxl")
    from openpyxl import load_workbook
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "w.xlsx"
        build_workbook(_sheet(), p, ref_cfg())
        wb = load_workbook(p)
        assert wb.sheetnames[0] == "Guide" and "Label" in wb.sheetnames
        ws = wb["Label"]
        assert [c.value for c in ws[1]] == COLUMNS and ws.max_row == 6
        assert ws["B2"].hyperlink.target.startswith("https://www.google.com/maps") and ws.freeze_panes == "C2"
        dvs = {str(r): dv for dv in ws.data_validations.dataValidation for r in dv.sqref.ranges}
        assert len(ws.data_validations.dataValidation) == 4
        assert any(dv.formula1 == "=lists!$A$1:$A$4" for dv in ws.data_validations.dataValidation)       # class_label dropdown
        assert ws["G2"].value == "unknown" and ws["G2"].number_format == "@" and ws["H2"].number_format == "@"
        guide = [[c.value for c in row] for row in wb["Guide"].iter_rows()]
        assert any(r[0] == "class_label" and r[1:] == ["loss", "no_loss", "uncertain", "ignore"] for r in guide)
        with pytest.raises(FileExistsError):
            build_workbook(_sheet(), p, ref_cfg())                                                       # never overwrites your work


def test_collect_checks_answers_and_writes_them_back_without_touching_other_columns():
    pytest.importorskip("openpyxl")
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "w.xlsx"
        build_workbook(_sheet(), p, ref_cfg())
        _fill(p, [
            {"class_label": "loss", "loss_type": "natural_to_built", "confidence": "medium", "evidence_source": "Google Earth Pro historical imagery",
             "evidence_before_date": 2022, "evidence_after_date": "2025", "notes": "new buildings"},
            {"class_label": " No_Loss ", "confidence": "high", "evidence_source": "Google Maps satellite"},
            {"class_label": "uncertain", "confidence": "low", "evidence_source": "Google Maps satellite"},
            {"class_label": "ignore", "confidence": "high"},
        ])
        rows = read_workbook(p)
        assert rows[0]["evidence_before_date"] == "2022" and rows[0]["evidence_after_date"] == "2025"      # numbers become text
        res = check_answers(rows, ref_cfg())
        assert res["errors"] == [] and res["unlabelled"] == ["C004_000"] and res["warnings"] == []
        new, problems = apply_to_sheet(_sheet(), rows)
        assert problems == [] and [r["class_label"] for r in new] == ["loss", "no_loss", "uncertain", "ignore", ""]
        assert new[1]["evidence_before_date"] == "unknown" and new[0]["maps_link"] == _sheet()[0]["maps_link"]
        assert all(r["reviewer_id"] == "R1" and r["lat"] == "28.3" for r in new)
        assert apply_to_sheet(_sheet(3), rows)[1]                                                          # extra workbook rows are reported


def test_collect_catches_the_mistakes_the_validator_would_reject():
    pytest.importorskip("openpyxl")
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "w.xlsx"
        build_workbook(_sheet(), p, ref_cfg())
        _fill(p, [
            {"class_label": "forest", "confidence": "high", "evidence_source": "x"},                                  # bad class
            {"class_label": "loss", "loss_type": "fire", "confidence": "high", "evidence_source": "x"},               # bad loss_type
            {"class_label": "no_loss", "confidence": "sure", "evidence_source": "x"},                                 # bad confidence
            {"class_label": "no_loss", "confidence": "high"},                                                         # no evidence source
            {"class_label": "no_loss", "confidence": "high", "evidence_source": "x", "evidence_after_date": "last year"},
        ])
        errs = " | ".join(check_answers(read_workbook(p), ref_cfg())["errors"])
        for frag in ("C000_000: class_label", "C001_000: loss_type", "C002_000: confidence", "C003_000: evidence_source", "C004_000: evidence_after_date"):
            assert frag in errs, frag
        _fill(p, [{"class_label": "loss", "confidence": "high", "evidence_source": "x"}, {"class_label": "no_loss", "loss_type": "other",
                                                                                         "confidence": "high", "evidence_source": "x"}])
        w = " | ".join(check_answers(read_workbook(p), ref_cfg())["warnings"])
        assert "C000_000: loss without a loss_type" in w and "C001_000: loss_type given" in w
