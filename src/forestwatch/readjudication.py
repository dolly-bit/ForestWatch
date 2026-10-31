"""Blind re-checking of reviewed candidates: what changed, and is it permanent vegetation loss?

The blank sheet contains NO detector information (no NDVI numbers, no seasonal flag, no earlier verdict)
and is shuffled, so the second look is independent of the first. Original labels are never edited.
"""
from __future__ import annotations
import csv
import random
from pathlib import Path

from .review_summary import classify_verdict, CANONICAL

CHANGE_TYPES = ("natural_vegetation_loss", "crop_cycle_or_field_change", "construction_or_road",
                "mining_or_quarry", "other_bare_ground", "no_visible_change", "cannot_tell")
EXPECTED_VERDICT = {"natural_vegetation_loss": "y", "construction_or_road": "y", "mining_or_quarry": "y",
                    "other_bare_ground": "y", "crop_cycle_or_field_change": "n", "no_visible_change": "n",
                    "cannot_tell": "?"}
BLANK_COLUMNS = ["id", "lat", "lon", "maps_link", "area_ha", "change_type", "verdict_v2", "confidence",
                 "evidence_date_seen", "notes"]
FILLED = ["change_type", "verdict_v2", "confidence", "evidence_date_seen", "notes"]


def make_blank_sheet(rows, seed: int = 1) -> list[dict]:
    rows = [r for r in rows if (r.get("id") or "").strip()]
    out = [{"id": r["id"], "lat": r.get("lat", ""), "lon": r.get("lon", ""), "maps_link": r.get("maps_link", ""),
            "area_ha": r.get("area_ha", ""), **{c: "" for c in FILLED}} for r in rows]
    random.Random(seed).shuffle(out)
    return out


def write_csv(path, rows, columns, overwrite: bool = False) -> None:
    path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} exists; refusing to overwrite your answers")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def validate_sheet(sheet_rows) -> dict:
    warnings, bad_types, bad_verdicts, inconsistent, empty = [], [], [], [], 0
    seen = set()
    for r in sheet_rows:
        i = (r.get("id") or "").strip()
        if i in seen:
            warnings.append(f"duplicate id {i} in the re-checking sheet (first one used)")
        seen.add(i)
        ct = (r.get("change_type") or "").strip()
        v = classify_verdict(r.get("verdict_v2"))
        if ct == "" and v == "unreviewed":
            empty += 1
            continue
        if ct not in CHANGE_TYPES:
            bad_types.append((i, ct))
        if v not in CANONICAL:
            bad_verdicts.append((i, r.get("verdict_v2")))
        elif ct in EXPECTED_VERDICT and EXPECTED_VERDICT[ct] != v:
            inconsistent.append((i, ct, v))
    if empty:
        warnings.append(f"{empty} row(s) not filled in yet")
    if bad_types:
        warnings.append(f"invalid change_type (allowed: {', '.join(CHANGE_TYPES)}): {bad_types[:8]}")
    if bad_verdicts:
        warnings.append(f"invalid or missing verdict_v2 (use y / n / ?): {bad_verdicts[:8]}")
    if inconsistent:
        warnings.append(f"change_type and verdict_v2 disagree with the protocol (check them): {inconsistent[:8]}")
    return {"warnings": warnings, "n_rows": len(sheet_rows), "n_unfilled": empty, "bad_types": bad_types,
            "bad_verdicts": bad_verdicts, "inconsistent": inconsistent}


def merge(original_rows, sheet_rows, landcover_classes=None, class_names=None) -> tuple[list[dict], list[str]]:
    """Original sheet + blind second look. Columns of the original sheet are kept unchanged."""
    by_id = {}
    for r in sheet_rows:
        by_id.setdefault((r.get("id") or "").strip(), r)
    merged, columns = [], list(original_rows[0].keys()) if original_rows else []
    extra = (["landcover_class", "landcover_name"] if landcover_classes is not None else []) + FILLED
    for k, r in enumerate(original_rows):
        row = dict(r)
        if landcover_classes is not None:
            row["landcover_class"] = landcover_classes[k]
            row["landcover_name"] = (class_names or {}).get(landcover_classes[k], "?")
        s = by_id.get((r.get("id") or "").strip(), {})
        for c in FILLED:
            row[c] = s.get(c, "")
        merged.append(row)
    return merged, columns + extra


def compare_passes(rows, first: str = "verdict", second: str = "verdict_v2") -> dict:
    """Agreement between two labelling passes on rows decided (y/n) in BOTH. Cohen's kappa corrects for chance."""
    pairs, skipped, disagreements = [], 0, []
    for r in rows:
        a, b = classify_verdict(r.get(first)), classify_verdict(r.get(second))
        if a in ("y", "n") and b in ("y", "n"):
            pairs.append((a, b))
            if a != b:
                disagreements.append({"id": r.get("id"), "first": a, "second": b,
                                      "change_type": r.get("change_type", ""), "landcover": r.get("landcover_name", "")})
        else:
            skipped += 1
    n = len(pairs)
    yy = sum(1 for a, b in pairs if a == "y" and b == "y")
    yn = sum(1 for a, b in pairs if a == "y" and b == "n")
    ny = sum(1 for a, b in pairs if a == "n" and b == "y")
    nn = sum(1 for a, b in pairs if a == "n" and b == "n")
    out = {"n_both_decided": n, "skipped_unsure_or_blank": skipped,
           "table": {"first_y_second_y": yy, "first_y_second_n": yn, "first_n_second_y": ny, "first_n_second_n": nn},
           "agreement": (yy + nn) / n if n else None, "kappa": None, "disagreements": disagreements}
    if n:
        po = (yy + nn) / n
        pe = ((yy + yn) / n) * ((yy + ny) / n) + ((ny + nn) / n) * ((yn + nn) / n)
        out["kappa"] = (po - pe) / (1 - pe) if pe < 1 else None
    return out
