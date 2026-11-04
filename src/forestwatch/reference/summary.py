"""Dataset summaries: counts AND areas by split, class, region, stratum and baseline status, plus provenance gaps."""
from __future__ import annotations
from collections import Counter

from .sampling import stratified_estimate

REPORT_NOTE = ("Chip labels are unit-level interpretations of imagery of mostly unknown date by one reviewer. "
               "Estimates assume the sampling design described in sampling_design.md and that uncertain/ignored chips are "
               "missing at random within strata (which may be false).")


def _table(rows, key, chip_area_ha):
    out: dict = {}
    for r in rows:
        k = r.get(key) or "(blank)"
        c = (r.get("class_label") or "(blank)")
        cell = out.setdefault(k, {}).setdefault(c, {"chips": 0, "area_ha": 0.0})
        cell["chips"] += 1
        cell["area_ha"] = round(cell["area_ha"] + chip_area_ha, 4)
    return out


def summarize_labels(label_rows, selected_rows, chip_area_ha: float) -> dict:
    pop = {r["unit_id"]: int(r["stratum_population"]) for r in selected_rows}
    out = {"n_labels": len(label_rows), "chip_area_ha": chip_area_ha,
           "by_split": _table(label_rows, "split", chip_area_ha), "by_region": _table(label_rows, "region", chip_area_ha),
           "by_stratum": _table(label_rows, "stratum", chip_area_ha),
           "by_baseline_status": _table(label_rows, "baseline_status", chip_area_ha),
           "by_reviewer": _table(label_rows, "reviewer_id", chip_area_ha),
           "versions": {"protocol": sorted({r["protocol_version"] for r in label_rows}),
                        "dataset": sorted({r["dataset_version"] for r in label_rows})},
           "provenance_gaps": {
               "missing_evidence_source": sum(not (r.get("evidence_source") or "").strip() and r.get("class_label") != "ignore" for r in label_rows),
               "missing_reviewer": sum(not (r.get("reviewer_id") or "").strip() for r in label_rows),
               "evidence_date_unknown": sum((r.get("evidence_before_date") or "").lower() == "unknown"
                                            or (r.get("evidence_after_date") or "").lower() == "unknown" for r in label_rows)},
           "excluded_area_ha": round(sum(chip_area_ha for r in label_rows if r.get("class_label") in ("uncertain", "ignore")), 4),
           "estimates": {}, "note": REPORT_NOTE}
    for split in sorted({r["split"] for r in label_rows}):
        units = [{"stratum": r["stratum"], "y": 1 if r["class_label"] == "loss" else 0, "N": pop[r["unit_id"]]}
                 for r in label_rows if r["split"] == split and r["class_label"] in ("loss", "no_loss") and r["unit_id"] in pop]
        if units:
            out["estimates"][split] = stratified_estimate(units)
    return out


def render_summary_md(s: dict) -> str:
    L = ["# Reference dataset summary (generated)", "", f"> {s['note']}", "",
         f"- Labels: {s['n_labels']} chips of {s['chip_area_ha']} ha each",
         f"- Protocol versions: {s['versions']['protocol']}; dataset versions: {s['versions']['dataset']}",
         f"- Excluded (uncertain or ignore) area: {s['excluded_area_ha']} ha",
         f"- Provenance gaps: {s['provenance_gaps']}"]
    for title, key in (("split", "by_split"), ("region", "by_region"), ("sampling stratum", "by_stratum"),
                       ("baseline status", "by_baseline_status"), ("reviewer", "by_reviewer")):
        L += ["", f"## By {title} (chips / hectares)"]
        for k, classes in s[key].items():
            L.append(f"- **{k}**: " + ", ".join(f"{c}: {v['chips']} / {v['area_ha']:.1f} ha" for c, v in sorted(classes.items())))
    L += ["", "## Provisional design-based estimates (loss chips in the whole sampling frame)"]
    if not s["estimates"]:
        L.append("- none (no decided chips)")
    for split, e in s["estimates"].items():
        L.append(f"- **{split}**: about {e['estimated_loss_chips']:.0f} of {e['population_chips']} eligible chips "
                 f"(95% interval {e['ci95'][0]:.0f} to {e['ci95'][1]:.0f}); prevalence {e['prevalence']:.1%}")
        L += [f"  - caveat: {n}" for n in e["notes"]]
    return "\n".join(L) + "\n"
