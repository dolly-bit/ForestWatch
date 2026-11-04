"""Counts, areas and provisional estimates for the reference labels. Test labels are excluded unless --final-evaluation.
  python scripts/summarize_reference_dataset.py --splits validation [--write-manifest]"""
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.audit import sha256_file, stack_metas, git_info
from forestwatch.reference.context import load_context
from forestwatch.reference.schema import read_rows, SPLITS, CLASSES, MASK_ENCODING, guard_test_labels
from forestwatch.reference.summary import summarize_labels, render_summary_md

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--splits", default="validation", help="comma-separated: train,validation,test")
ap.add_argument("--final-evaluation", action="store_true")
ap.add_argument("--write-manifest", action="store_true")
args = ap.parse_args()
splits = guard_test_labels([s for s in args.splits.split(",") if s], args.final_evaluation)
bad = [s for s in splits if s not in SPLITS]
if bad:
    sys.exit(f"unknown split(s): {bad}")
cfg, ref, meta, shape = load_context(ROOT)
d = ROOT / "data" / "reference"
labels, selected = [], []
for s in splits:
    labels += read_rows(d / f"labels_{s}.csv")
    selected += read_rows(d / f"selected_units_{s}.csv")
chip_ha = (ref["chip_px"] * cfg["region"]["resolution_m"]) ** 2 / 10000.0
summary = summarize_labels(labels, selected, chip_ha)
out = ROOT / "reports" / "phase2"
out.mkdir(parents=True, exist_ok=True)
(out / "dataset_summary.generated.md").write_text(render_summary_md(summary), encoding="utf-8")
(out / "dataset_summary.generated.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
print(render_summary_md(summary))
if args.write_manifest:
    files = {p.name: sha256_file(p) for p in sorted(d.glob("*.csv")) if p.name.startswith(("sampling_frame", "selected_units", "labels_"))}
    manifest = {"dataset_version": ref["dataset_version"], "protocol_version": ref["protocol_version"],
                "created_utc": datetime.now(timezone.utc).isoformat(), "study_area": {"bbox_lonlat": cfg["region"]["bbox"], "crs": meta["crs"]},
                "grid": {"width": meta["width"], "height": meta["height"], "transform": meta["transform"], "resolution_m": cfg["region"]["resolution_m"]},
                "imagery": {"catalog": cfg["stac"]["url"], "collection": cfg["stac"]["collection"], "windows": cfg["windows"],
                            "scenes": [{k: m[k] for k in ("window", "scene_id", "date")} for m in stack_metas(ROOT)]},
                "classes": list(CLASSES), "mask_encoding": MASK_ENCODING,
                "reference_unit": f"chip of {ref['chip_px']} x {ref['chip_px']} pixels ({chip_ha:.2f} ha)",
                "sampling": "stratified random sampling without replacement within split x (baseline status | land-cover group); "
                            "inclusion probabilities stored per unit",
                "split_manifest": json.loads((ROOT / "data" / "splits" / "frozen.json").read_text()) if (ROOT / "data" / "splits" / "frozen.json").exists() else None,
                "review_method": "single reviewer, blind to model output, imagery of mostly unknown date (see reference_labeling_protocol.md)",
                "known_limitations": "see reports/phase2/limitations.md", "git": git_info(ROOT), "file_sha256": files}
    (d / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print("Wrote data/reference/dataset_manifest.json")
