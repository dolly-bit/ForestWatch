"""Second-pass (blind re-review) support and agreement statistics for chip labels."""
from __future__ import annotations
import random


def cohen_kappa(a, b):
    n = len(a)
    if n == 0 or n != len(b):
        return None
    cats = set(a) | set(b)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return None if pe >= 1 else (po - pe) / (1 - pe)


def rereview_ids(label_rows, fraction: float, seed: int) -> list[str]:
    ids = sorted(r["unit_id"] for r in label_rows)
    k = max(1, round(fraction * len(ids))) if ids else 0
    return sorted(random.Random(seed).sample(ids, min(k, len(ids))))


def compare_reference_passes(first_rows, second_rows) -> dict:
    """Agreement on all four classes between the original labels and the blind re-review (matched by unit_id)."""
    second = {r["unit_id"]: (r.get("class_label") or "").strip() for r in second_rows if (r.get("class_label") or "").strip()}
    pairs = [((r.get("class_label") or "").strip(), second[r["unit_id"]]) for r in first_rows if r["unit_id"] in second]
    a, b = [p[0] for p in pairs], [p[1] for p in pairs]
    n = len(pairs)
    table: dict = {}
    for x, y in pairs:
        table[f"{x} -> {y}"] = table.get(f"{x} -> {y}", 0) + 1
    return {"n_compared": n, "agreement": (sum(x == y for x, y in pairs) / n) if n else None,
            "kappa": cohen_kappa(a, b), "table": table,
            "disagreements": [r["unit_id"] for r in first_rows if r["unit_id"] in second
                              and (r.get("class_label") or "").strip() != second[r["unit_id"]]]}
