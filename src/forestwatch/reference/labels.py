"""Blind label sheets, merging answers into label records, and validation."""
from __future__ import annotations
import random
from collections import Counter
from datetime import date

from .export import chip_center, maps_link
from .schema import CLASSES, SHEET_COLUMNS, LABEL_COLUMNS, SPLITS

FILL = ["class_label", "loss_type", "confidence", "evidence_source", "evidence_before_date", "evidence_after_date",
        "event_start", "event_end", "review_date", "notes"]


def make_label_sheet(selected_rows, transform, crs, reviewer_id: str, seed: int = 1) -> list[dict]:
    """Blind and shuffled: only the unit id, location and link. No stratum, baseline status or probability."""
    out = []
    for r in selected_rows:
        lat, lon = chip_center(r, transform, crs)
        out.append({"unit_id": r["unit_id"], "lat": lat, "lon": lon, "maps_link": maps_link(lat, lon),
                    **{c: "" for c in FILL}, "reviewer_id": reviewer_id})
    random.Random(seed).shuffle(out)
    return out


def merge_labels(sheet_rows, selected_rows, ref_cfg, ingestion_date: str, crs: str):
    """Join answers with the (hidden) sampling information. Returns (label_rows, unlabelled_unit_ids)."""
    units = {r["unit_id"]: r for r in selected_rows}
    labels, unlabelled = [], []
    for s in sheet_rows:
        uid = (s.get("unit_id") or "").strip()
        u = units.get(uid)
        if u is None:
            raise ValueError(f"sheet row {uid!r} is not one of the selected units")
        cls = (s.get("class_label") or "").strip()
        if cls == "":
            unlabelled.append(uid)
            continue
        labels.append({"label_id": f"L-{uid}", "unit_id": uid, "block_id": u["block_id"], "split": u["split"],
                       "class_label": cls, "loss_type": (s.get("loss_type") or "").strip(),
                       "event_start": (s.get("event_start") or "").strip(), "event_end": (s.get("event_end") or "").strip(),
                       "evidence_source": (s.get("evidence_source") or "").strip(),
                       "evidence_before_date": (s.get("evidence_before_date") or "").strip(),
                       "evidence_after_date": (s.get("evidence_after_date") or "").strip(),
                       "reviewer_id": (s.get("reviewer_id") or "").strip(),
                       "review_date": (s.get("review_date") or "").strip() or ingestion_date,
                       "confidence": (s.get("confidence") or "").strip().lower(), "review_status": "labelled",
                       "notes": (s.get("notes") or "").strip(), "protocol_version": ref_cfg["protocol_version"],
                       "dataset_version": ref_cfg["dataset_version"], "region": u["region"], "stratum": u["stratum"],
                       "baseline_status": u["baseline_status"], "selection_probability": u["selection_probability"],
                       "chip_row0": u["chip_row0"], "chip_row1": u["chip_row1"], "chip_col0": u["chip_col0"],
                       "chip_col1": u["chip_col1"], "crs": crs})
    return labels, unlabelled


def _parse_partial(text):
    """Imagery dates are often known only to the year or month: accept YYYY, YYYY-MM, YYYY-MM-DD or 'unknown'."""
    t = (text or "").strip()
    if t == "":
        return "empty"
    if t.lower() == "unknown":
        return "unknown"
    parts = t.split("-")
    try:
        if len(parts) == 1 and len(t) == 4:
            return "ok" if 1900 <= int(t) <= 2100 else "invalid"
        if len(parts) == 2 and len(parts[0]) == 4 and len(parts[1]) == 2:
            return "ok" if 1 <= int(parts[1]) <= 12 and 1900 <= int(parts[0]) <= 2100 else "invalid"
        if len(parts) == 3:
            date.fromisoformat(t)
            return "ok"
    except ValueError:
        pass
    return "invalid"


def _parse(text, allow_unknown=False):
    t = (text or "").strip()
    if t == "":
        return None, "empty"
    if allow_unknown and t.lower() == "unknown":
        return None, "unknown"
    try:
        return date.fromisoformat(t), "ok"
    except ValueError:
        return None, "invalid"


def validate_labels(rows, blocks, shape, chip_px: int, block_px: int, ref_cfg) -> dict:
    """blocks: prepare_blocks() output of the FROZEN manifest. Returns {errors, warnings, counts}."""
    errors, warnings = [], []
    H, W = shape
    block_by_id = {int(b["block_id"]): b for b in blocks}
    block_by_pos = {(b["row_block"], b["col_block"]): b for b in blocks}
    if not rows:
        return {"errors": ["no label rows"], "warnings": [], "counts": {}}
    missing_cols = [c for c in LABEL_COLUMNS if c not in rows[0]]
    if missing_cols:
        errors.append(f"missing columns: {missing_cols}")
    for name in ("label_id", "unit_id"):
        ids = [(r.get(name) or "").strip() for r in rows]
        if any(i == "" for i in ids):
            errors.append(f"empty {name} on {sum(i == '' for i in ids)} row(s)")
        dup = sorted(i for i, c in Counter(ids).items() if i and c > 1)
        if dup:
            errors.append(f"duplicate {name}: {dup[:8]}")
    seen_pos = {}
    for r in rows:
        uid = r.get("unit_id", "?")
        tag = f"{uid}"
        cls = (r.get("class_label") or "").strip()
        if cls not in CLASSES:
            errors.append(f"{tag}: class_label {cls!r} not in {list(CLASSES)} (uncertain must stay 'uncertain', never 'no_loss')")
        lt = (r.get("loss_type") or "").strip()
        if cls == "loss" and lt == "":
            warnings.append(f"{tag}: loss without loss_type")
        if lt and lt not in ref_cfg["loss_types"]:
            errors.append(f"{tag}: loss_type {lt!r} not in {ref_cfg['loss_types']}")
        if lt and cls != "loss":
            warnings.append(f"{tag}: loss_type given for class {cls!r}")
        if (r.get("confidence") or "").strip() not in ref_cfg["confidence_scale"]:
            errors.append(f"{tag}: confidence {r.get('confidence')!r} not in {ref_cfg['confidence_scale']}")
        if cls != "ignore" and not (r.get("evidence_source") or "").strip():
            errors.append(f"{tag}: evidence_source is required")
        for f in ("reviewer_id", "protocol_version", "dataset_version"):
            if not (r.get(f) or "").strip():
                errors.append(f"{tag}: {f} is required")
        d, st = _parse(r.get("review_date"))
        if st != "ok":
            errors.append(f"{tag}: review_date {st} ({r.get('review_date')!r})")
        for f in ("evidence_before_date", "evidence_after_date"):
            if _parse_partial(r.get(f)) in ("invalid", "empty"):
                errors.append(f"{tag}: {f} must be YYYY, YYYY-MM, YYYY-MM-DD or 'unknown' (got {r.get(f)!r})")
        es, st1 = _parse(r.get("event_start"))
        ee, st2 = _parse(r.get("event_end"))
        if "invalid" in (st1, st2):
            errors.append(f"{tag}: event_start/event_end must be YYYY-MM-DD or empty")
        elif es and ee and es > ee:
            errors.append(f"{tag}: event_start {es} is after event_end {ee}")
        try:
            r0, r1, c0, c1 = (int(r[k]) for k in ("chip_row0", "chip_row1", "chip_col0", "chip_col1"))
        except (KeyError, ValueError):
            errors.append(f"{tag}: chip bounds missing or not integers")
            continue
        if not (0 <= r0 < r1 <= H and 0 <= c0 < c1 <= W):
            errors.append(f"{tag}: chip lies outside the study grid {H}x{W}")
            continue
        if (r1 - r0, c1 - c0) != (chip_px, chip_px) or r0 % chip_px or c0 % chip_px:
            errors.append(f"{tag}: chip is not an aligned {chip_px}x{chip_px} square")
        b = block_by_pos.get((r0 // block_px, c0 // block_px))
        if b is None or (r1 - 1) // block_px != r0 // block_px or (c1 - 1) // block_px != c0 // block_px:
            errors.append(f"{tag}: chip does not sit inside one block")
        else:
            if str(r.get("block_id")) != str(b["block_id"]):
                errors.append(f"{tag}: block_id {r.get('block_id')} but the chip is in block {b['block_id']}")
            if r.get("split") != b["split"]:
                errors.append(f"{tag}: split {r.get('split')!r} but its block is {b['split']!r} in the frozen manifest")
            if b["split"] not in SPLITS:
                errors.append(f"{tag}: chip is in a {b['split']!r} block; only {list(SPLITS)} may be labelled")
        key = (r0, c0)
        if key in seen_pos:
            errors.append(f"{tag} overlaps {seen_pos[key]}: contradictory labels for the same area")
        seen_pos[key] = uid
        try:
            if not 0 < float(r.get("selection_probability")) <= 1:
                raise ValueError
        except (TypeError, ValueError):
            warnings.append(f"{tag}: selection_probability missing or outside (0, 1]")
    return {"errors": errors, "warnings": warnings,
            "counts": {"rows": len(rows), "by_class": dict(Counter((r.get("class_label") or "").strip() for r in rows))}}
