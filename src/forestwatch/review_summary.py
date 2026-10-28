"""Candidate-level review statistics, validated and reproducible.

These are REVIEWER-VERDICT statistics on a sample of detections. They are NOT validated pixel-level
precision/recall, and they say nothing about how much real loss the detector missed.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from .review import normalize_verdict, wilson_ci

REQUIRED_COLUMNS = ["id", "area_ha", "mean_ndvi_drop", "kept_by_seasonal", "lat", "lon", "verdict"]
NUMERIC_COLUMNS = ["area_ha", "mean_ndvi_drop", "lat", "lon"]
CANONICAL = ("y", "n", "?")
ANNOTATION_COLUMNS = ["candidate_id", "reviewer", "review_date", "verdict", "confidence",
                      "evidence_source", "evidence_date", "notes"]
STATEMENT = ("These are reviewer verdict statistics on a sample of candidate detections. They are not validated "
             "pixel-level precision or recall, and they cannot show how much real vegetation loss was missed.")


class ReviewInputError(Exception):
    pass


def read_review_csv(path):
    path = Path(path)
    if not path.exists():
        raise ReviewInputError(f"File not found: {path}")
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        cols = list(reader.fieldnames or [])
    return rows, cols


def classify_verdict(raw) -> str:
    """'y' / 'n' / '?' / 'unreviewed' (blank) / 'invalid' (anything else)."""
    text = (raw or "").strip()
    if text == "":
        return "unreviewed"
    v = normalize_verdict(text)
    return v if v in CANONICAL else "invalid"


def _isfinite(text) -> bool:
    try:
        return math.isfinite(float(text))
    except (TypeError, ValueError):
        return False


def validate(rows, columns) -> dict:
    errors, warnings = [], []
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing_cols:
        errors.append(f"Missing required columns: {missing_cols}")
    if not rows:
        errors.append("No data rows in the file")
    ids = [(r.get("id") or "").strip() for r in rows]
    dup = sorted(i for i, c in Counter(ids).items() if i and c > 1)
    if dup:
        warnings.append(f"Duplicate ids (only the first occurrence is counted): {dup[:10]}")
    missing_values = {c: sum(1 for r in rows if (r.get(c) or "").strip() == "")
                      for c in REQUIRED_COLUMNS if c in columns and c != "verdict"}
    for c, n in missing_values.items():
        if n:
            warnings.append(f"{n} row(s) have an empty '{c}'")
    nonfinite = {c: sum(1 for r in rows if (r.get(c) or "").strip() != "" and not _isfinite(r.get(c)))
                 for c in NUMERIC_COLUMNS if c in columns}
    for c, n in nonfinite.items():
        if n:
            warnings.append(f"{n} row(s) have a non-numeric or non-finite '{c}'")
    spellings = Counter()
    invalid = []
    if "verdict" in columns:
        for r in rows:
            raw = (r.get("verdict") or "").strip()
            cls = classify_verdict(raw)
            if cls == "invalid":
                invalid.append({"id": (r.get("id") or "").strip(), "value": raw})
            elif cls in CANONICAL and raw.lower() not in CANONICAL:
                spellings[raw] += 1
    if invalid:
        warnings.append(f"{len(invalid)} row(s) have an unrecognised verdict (excluded from rates): "
                        f"{[i['value'] for i in invalid][:10]}")
    if spellings:
        warnings.append(f"Non-canonical verdict spellings were normalised: {dict(spellings)} (use y / n / ?)")
    return {"n_rows": len(rows), "unique_ids": len({i for i in ids if i}), "duplicate_ids": dup,
            "missing_columns": missing_cols, "missing_values": missing_values, "nonfinite_values": nonfinite,
            "invalid_verdicts": invalid, "normalised_spellings": dict(spellings),
            "errors": errors, "warnings": warnings}


def _rate_block(rows) -> dict:
    counts = Counter(classify_verdict(r.get("verdict")) for r in rows)
    y, n, u = counts["y"], counts["n"], counts["?"]
    decided = y + n
    rate = (y / decided) if decided else None
    lo, hi = wilson_ci(y, decided) if decided else (None, None)
    reviewed = decided + u
    return {"rows": len(rows), "y": y, "n": n, "unsure": u, "unreviewed": counts["unreviewed"],
            "invalid": counts["invalid"], "decided": decided,
            "positive_rate_among_decided": rate, "ci95_wilson": [lo, hi] if decided else None,
            "rate_among_all_reviewed_with_unsure_as_not_positive": (y / reviewed) if reviewed else None,
            "sensitivity_to_unsure": ({"all_unsure_negative": y / reviewed, "all_unsure_positive": (y + u) / reviewed}
                                      if reviewed else None)}


def summarize(rows, columns, meta: dict | None = None, population_size: int | None = None,
              group_by: str = "kept_by_seasonal", input_path: str = "", input_sha256: str = "") -> dict:
    validation = validate(rows, columns)
    seen, kept_rows = set(), []
    for r in rows:                                   # first occurrence of each non-blank id
        i = (r.get("id") or "").strip()
        if i and i in seen:
            continue
        seen.add(i)
        kept_rows.append(r)
    out = {"input": {"path": input_path, "sha256": input_sha256}, "validation": validation,
           "statement": STATEMENT, "sampling": None, "overall": None, "by_group": {}, "population_estimate": None}
    if validation["errors"]:
        return out
    out["overall"] = _rate_block(kept_rows)
    if group_by in columns:
        groups = {}
        for r in kept_rows:
            groups.setdefault((r.get(group_by) or "").strip() or "(blank)", []).append(r)
        out["by_group"] = {"column": group_by, "groups": {k: _rate_block(v) for k, v in sorted(groups.items())},
                           "note": "Post-hoc subgroups of one sample (not pre-defined strata); small groups are imprecise."}
    if meta:
        out["sampling"] = {k: meta.get(k) for k in ("method", "total_candidates", "eligible", "min_area_ha",
                                                     "sampled", "seed", "kept_by_seasonal_total", "pages")}
        population_size = population_size or meta.get("eligible")
    o = out["overall"]
    if population_size and o["positive_rate_among_decided"] is not None:
        n, N = o["decided"], population_size
        lo, hi = o["ci95_wilson"]
        out["population_estimate"] = {
            "population_size": N, "decided_sample": n, "sampling_fraction": n / N,
            "finite_population_factor": math.sqrt((N - n) / (N - 1)) if N > 1 and n <= N else None,
            "expected_positive_candidates": o["positive_rate_among_decided"] * N,
            "expected_positive_candidates_ci95": [lo * N, hi * N],
            "assumptions": ["simple random sample from the stated population", "reviewer verdicts treated as truth",
                            "'?' and unreviewed rows excluded", "Wilson interval not adjusted for finite population"]}
    return out


def _fmt(x, pct=True):
    if x is None:
        return "undefined"
    return f"{x:.1%}" if pct else f"{x:.2f}"


def _block_md(b: dict) -> list[str]:
    lines = [f"- Rows: {b['rows']} | y: {b['y']} | n: {b['n']} | ?: {b['unsure']} | unreviewed: {b['unreviewed']} | "
             f"invalid: {b['invalid']}",
             f"- Decided cases (y + n): {b['decided']}",
             f"- Positive-verdict rate among decided: **{_fmt(b['positive_rate_among_decided'])}**"]
    if b["ci95_wilson"]:
        lines.append(f"- 95% Wilson interval: {_fmt(b['ci95_wilson'][0])} to {_fmt(b['ci95_wilson'][1])}")
    if b["sensitivity_to_unsure"]:
        s = b["sensitivity_to_unsure"]
        lines.append(f"- If every '?' were negative: {_fmt(s['all_unsure_negative'])}; if every '?' were positive: "
                     f"{_fmt(s['all_unsure_positive'])}")
    return lines


def render_markdown(s: dict) -> str:
    L = ["# Review summary (candidate level)", "", f"> {s['statement']}", "",
         "## Input and validation", f"- File: `{s['input']['path']}`", f"- SHA-256: `{s['input']['sha256']}`"]
    v = s["validation"]
    L += [f"- Rows: {v['n_rows']} | unique ids: {v['unique_ids']} | duplicate ids: {len(v['duplicate_ids'])}",
          f"- Missing columns: {v['missing_columns'] or 'none'}"]
    if v["errors"]:
        L += ["", "### ERRORS (no statistics produced)"] + [f"- {e}" for e in v["errors"]]
        return "\n".join(L) + "\n"
    L += ["", "### Warnings"] + ([f"- {w}" for w in v["warnings"]] or ["- none"])
    if s["sampling"]:
        sp = s["sampling"]
        L += ["", "## Sampling (from review_meta.json)",
              f"- Frame: {sp['total_candidates']} candidates in total, {sp['eligible']} eligible "
              f"(area >= {sp['min_area_ha']} ha)",
              f"- Sample: {sp['sampled']} drawn uniformly without replacement, seed {sp['seed']}; not stratified",
              "- The seasonal filter flag was computed after sampling (sampling was done before filtering)"]
    L += ["", "## Verdicts, all rows"] + _block_md(s["overall"])
    if s["by_group"]:
        L += ["", f"## By `{s['by_group']['column']}`", f"_{s['by_group']['note']}_"]
        for k, b in s["by_group"]["groups"].items():
            L += ["", f"### {k}"] + _block_md(b)
            if b["decided"] < 10:
                L.append("- WARNING: fewer than 10 decided cases; treat as anecdotal")
    pe = s["population_estimate"]
    if pe:
        fpc = f"{pe['finite_population_factor']:.3f}" if pe["finite_population_factor"] is not None else "n/a"
        L += ["", "## Extrapolation to the sampling frame (provisional)",
              f"- Population {pe['population_size']}; sampled {pe['decided_sample']} decided "
              f"({pe['sampling_fraction']:.1%}); finite-population factor {fpc}",
              f"- Expected positive candidates: {pe['expected_positive_candidates']:.0f} "
              f"(95%: {pe['expected_positive_candidates_ci95'][0]:.0f} to {pe['expected_positive_candidates_ci95'][1]:.0f})",
              "- Assumptions: " + "; ".join(pe["assumptions"])]
    L += ["", "## Not available from this file",
          "- Recall (needs reference loss areas including places the detector did not flag)",
          "- Pixel-level precision, F1, IoU, false alarms per 100 km2 (need aligned reference masks)"]
    return "\n".join(L) + "\n"


def init_annotations(rows, out_path, overwrite: bool = False) -> int:
    """Create the audit-trail template; never overwrites existing annotations unless asked."""
    out_path = Path(out_path)
    if out_path.exists() and not overwrite:
        raise FileExistsError(f"{out_path} exists; refusing to overwrite annotations")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ANNOTATION_COLUMNS)
        w.writeheader()
        for r in rows:
            cls = classify_verdict(r.get("verdict"))
            w.writerow({"candidate_id": r.get("id"), "reviewer": "", "review_date": "",
                        "verdict": cls if cls in CANONICAL else "", "confidence": "",
                        "evidence_source": "", "evidence_date": "", "notes": ""})
    return len(rows)


def sha256_of(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def dumps_json(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)
