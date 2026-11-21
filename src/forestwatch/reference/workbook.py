"""Excel label workbook with dropdown menus (needs openpyxl), and the step that writes your answers back to the CSV.

Why: the validator is strict about spelling (loss / no_loss / uncertain / ignore ...). Dropdowns remove typos; the
workbook also carries a guide sheet. Your judgments are still entirely yours: nothing is pre-filled except the two
imagery dates ('unknown' until you see a year)."""
from __future__ import annotations
from datetime import date, datetime

from .labels import _parse_partial, _parse
from .schema import CLASSES

LABEL_SHEET = "Label"
COLUMNS = ["unit_id", "maps_link", "class_label", "loss_type", "confidence", "evidence_source",
           "evidence_before_date", "evidence_after_date", "notes"]
FILL_COLUMNS = ["class_label", "loss_type", "confidence", "evidence_source", "evidence_before_date",
                "evidence_after_date", "notes"]
EVIDENCE_CHOICES = ["Google Maps satellite", "Google Earth Pro historical imagery", "Google Earth web", "Other (say which in notes)"]

# (column, loss, no_loss, uncertain, ignore)
GUIDE = [
    ("class_label", "loss", "no_loss", "uncertain", "ignore"),
    ("What you see", "A cleared / built / mined patch of at least ~55 m x 55 m (0.3 ha) that was trees, scrub or grass before and is bare, built or mined now",
     "Trees, scrub or grass throughout; farm fields (even bare ones); buildings that were clearly already there; farmland turned into buildings (write 'field to buildings' in notes)",
     "You cannot tell: blurry, shadows, mixed, or the photo is too old / too new to show the change", "Cloud over the square, water only, or no imagery"),
    ("loss_type", "REQUIRED: natural_to_bare, natural_to_built, natural_to_mining or other", "leave EMPTY", "leave EMPTY", "leave EMPTY"),
    ("confidence", "high / medium / low", "high / medium / low", "usually low", "high"),
    ("evidence_source", "pick from the list", "pick from the list", "pick from the list", "pick from the list"),
    ("evidence_before_date", "year of the older photo, or unknown", "year, or unknown", "year, or unknown", "unknown"),
    ("evidence_after_date", "year of the newer photo, or unknown", "year, or unknown", "year, or unknown", "unknown"),
    ("notes", "what changed, e.g. 'new buildings where scrub was'", "optional, e.g. 'field to buildings'", "why you are unsure", "why it cannot be assessed"),
    ("event_start / event_end / review_date / reviewer_id", "leave as they are (not in the workbook)", "same", "same", "same"),
]
RULES = [
    "Judge the WHOLE 320 m square, not only the centre pin.",
    "Never guess: if you hesitate for more than about a minute, choose uncertain. It is excluded from results and is not a failure.",
    "Farm fields are no_loss, bare or not. Do not use detector output, NDVI numbers or the sampling stratum.",
    "A single photo cannot show change over time: use Google Earth Pro's time slider, or lower the confidence.",
    "Dates: a year such as 2024, or the word unknown. Never guess a date.",
]


def build_workbook(sheet_rows, path, ref_cfg, overwrite: bool = False):
    from pathlib import Path
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} exists; refusing to overwrite your work")
    wb = Workbook()
    ws = wb.active
    ws.title = LABEL_SHEET
    head_fill, you_fill = PatternFill("solid", fgColor="D9D9D9"), PatternFill("solid", fgColor="FFF2CC")
    for j, name in enumerate(COLUMNS, start=1):
        c = ws.cell(row=1, column=j, value=name)
        c.font, c.fill = Font(bold=True), (you_fill if name in FILL_COLUMNS else head_fill)
    hints = {"class_label": "loss / no_loss / uncertain / ignore (see the Guide sheet)",
             "loss_type": "only for loss: " + ", ".join(ref_cfg["loss_types"]),
             "confidence": " / ".join(ref_cfg["confidence_scale"]),
             "evidence_before_date": "a year (2022) or unknown. Never guess.",
             "evidence_after_date": "a year (2024) or unknown. Never guess."}
    for name, text in hints.items():
        ws.cell(row=1, column=COLUMNS.index(name) + 1).comment = Comment(text, "ForestWatch")
    for i, r in enumerate(sheet_rows, start=2):
        ws.cell(row=i, column=1, value=r["unit_id"])
        link = ws.cell(row=i, column=2, value="open map")
        link.hyperlink, link.font = r["maps_link"], Font(color="0563C1", underline="single")
        for name in FILL_COLUMNS:
            v = (r.get(name) or "").strip()
            if name in ("evidence_before_date", "evidence_after_date") and not v:
                v = "unknown"
            ws.cell(row=i, column=COLUMNS.index(name) + 1, value=v or None)
        for name in ("evidence_before_date", "evidence_after_date", "notes", "evidence_source"):
            ws.cell(row=i, column=COLUMNS.index(name) + 1).number_format = "@"        # keep '2024' / '2024-07' as typed
    last = max(len(sheet_rows) + 1, 2)
    lists = wb.create_sheet("lists")
    lists.sheet_state = "hidden"
    for j, vals in enumerate([list(CLASSES), list(ref_cfg["loss_types"]), list(ref_cfg["confidence_scale"]), EVIDENCE_CHOICES], start=1):
        for i, v in enumerate(vals, start=1):
            lists.cell(row=i, column=j, value=v)
    sources = {"class_label": ("A", len(CLASSES), True), "loss_type": ("B", len(ref_cfg["loss_types"]), True),
               "confidence": ("C", len(ref_cfg["confidence_scale"]), True), "evidence_source": ("D", len(EVIDENCE_CHOICES), False)}
    for name, (col, n, strict) in sources.items():
        dv = DataValidation(type="list", formula1=f"=lists!${col}$1:${col}${n}", allow_blank=True,
                            showErrorMessage=True, errorStyle="stop" if strict else "warning",
                            error="Pick a value from the list." if strict else "Not in the list: fine if you really used another source (then say which in notes).")
        ws.add_data_validation(dv)
        L = chr(ord("A") + COLUMNS.index(name))
        dv.add(f"{L}2:{L}{last}")
    for L, w in zip("ABCDEFGHI", (12, 11, 14, 20, 12, 34, 20, 20, 44)):
        ws.column_dimensions[L].width = w
    ws.freeze_panes = "C2"
    g = wb.create_sheet("Guide", 0)
    g["A1"], g["A1"].font = "How to fill the Label sheet (yellow columns)", Font(bold=True, size=13)
    for i, rule in enumerate(RULES, start=3):
        c = g.cell(row=i, column=1, value=f"{i - 2}. {rule}")
        g.merge_cells(start_row=i, start_column=1, end_row=i, end_column=5)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        g.row_dimensions[i].height = 30
    top = 3 + len(RULES) + 1
    for i, row in enumerate(GUIDE):
        for j, v in enumerate(row, start=1):
            c = g.cell(row=top + i, column=j, value=v)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            if i == 0 or j == 1:
                c.font = Font(bold=True)
    for L, w in zip("ABCDE", (26, 46, 46, 34, 30)):
        g.column_dimensions[L].width = w
    for sheet in (g, ws):                                   # printable: landscape, one page wide
        sheet.page_setup.orientation = "landscape"
        sheet.page_setup.fitToWidth, sheet.page_setup.fitToHeight = 1, 0
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
    wb.save(path)


def _text(v):
    if v is None:
        return "", None
    if isinstance(v, (datetime, date)):
        return v.strftime("%Y-%m-%d"), "Excel turned a date answer into a real date; retype it as text (for example 2024)"
    if isinstance(v, float) and v.is_integer():
        return str(int(v)), None
    return str(v).strip(), None


def read_workbook(path) -> list[dict]:
    from openpyxl import load_workbook
    ws = load_workbook(path, data_only=True)[LABEL_SHEET]
    header = {str(c.value).strip(): j for j, c in enumerate(ws[1]) if c.value}
    rows = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        uid = r[header["unit_id"]]
        if uid in (None, ""):
            continue
        row, warn = {"unit_id": str(uid).strip()}, []
        for name in FILL_COLUMNS:
            if name in header:
                t, w = _text(r[header[name]])
                row[name] = t
                if w:
                    warn.append(f"{row['unit_id']}: {name}: {w}")
        row["_warnings"] = warn
        rows.append(row)
    return rows


def check_answers(wb_rows, ref_cfg) -> dict:
    """Problems in the answers, mirroring what validate_reference_labels.py will insist on."""
    errors, warnings, unlabelled = [], [], []
    for r in wb_rows:
        warnings += r.get("_warnings", [])
        u = r["unit_id"]
        cls = r["class_label"].lower()
        if cls == "":
            unlabelled.append(u)
            continue
        if cls not in CLASSES:
            errors.append(f"{u}: class_label {r['class_label']!r} is not one of {list(CLASSES)}")
        lt = r["loss_type"].lower()
        if lt and lt not in ref_cfg["loss_types"]:
            errors.append(f"{u}: loss_type {r['loss_type']!r} is not one of {ref_cfg['loss_types']}")
        if cls == "loss" and not lt:
            warnings.append(f"{u}: loss without a loss_type")
        if lt and cls != "loss":
            warnings.append(f"{u}: loss_type given but class is {cls!r} (clear loss_type unless it applies)")
        if r["confidence"].lower() not in ref_cfg["confidence_scale"]:
            errors.append(f"{u}: confidence {r['confidence']!r} must be one of {ref_cfg['confidence_scale']}")
        if cls != "ignore" and not r["evidence_source"]:
            errors.append(f"{u}: evidence_source is empty")
        for f in ("evidence_before_date", "evidence_after_date"):
            if _parse_partial(r[f]) in ("invalid", "empty"):
                errors.append(f"{u}: {f} must be a year, YYYY-MM, YYYY-MM-DD or 'unknown' (got {r[f]!r})")
    return {"errors": errors, "warnings": warnings, "unlabelled": unlabelled}


def apply_to_sheet(sheet_rows, wb_rows):
    """Copy answers into the CSV rows (same order, other columns untouched). Returns (rows, problems)."""
    by = {r["unit_id"]: r for r in wb_rows}
    problems = [f"{u} is in the workbook but not in the label sheet" for u in by if u not in {s["unit_id"] for s in sheet_rows}]
    out = []
    for s in sheet_rows:
        s = dict(s)
        w = by.get(s["unit_id"])
        if w is None:
            problems.append(f"{s['unit_id']} is missing from the workbook")
        else:
            for name in FILL_COLUMNS:
                v = w[name]
                s[name] = v.lower() if name in ("class_label", "loss_type", "confidence") else v
        out.append(s)
    return out, problems
