"""Blind re-review of a random subset of your labels (quality check; never edits the originals).
  python scripts/rereview.py make    --split validation [--fraction 0.2]   -> data/reference/rereview_sheet_<split>.csv
  python scripts/rereview.py compare --split validation                    -> agreement + kappa
Wait at least a few days between the first pass and the re-review, and do not open the first labels."""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.reference.context import load_context
from forestwatch.reference.schema import read_rows, write_rows, SPLITS, SHEET_COLUMNS
from forestwatch.reference.labels import make_label_sheet
from forestwatch.reference.qa import rereview_ids, compare_reference_passes

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("action", choices=["make", "compare"])
ap.add_argument("--split", required=True, choices=SPLITS)
ap.add_argument("--fraction", type=float, default=0.2)
ap.add_argument("--reviewer", default="R1-rereview")
args = ap.parse_args()
cfg, ref, meta, shape = load_context(ROOT)
d = ROOT / "data" / "reference"
labels = read_rows(d / f"labels_{args.split}.csv")
path = d / f"rereview_sheet_{args.split}.csv"
if args.action == "make":
    ids = set(rereview_ids(labels, args.fraction, ref["seed"]))
    chosen = [r for r in labels if r["unit_id"] in ids]
    write_rows(path, make_label_sheet(chosen, tuple(meta["transform"]), meta["crs"], args.reviewer, seed=7), SHEET_COLUMNS)
    print(f"Wrote {len(ids)} blind chips to {path}. Fill class_label (and evidence_source) only.")
else:
    res = compare_reference_passes(labels, read_rows(path))
    print(json.dumps(res, indent=2))
    (ROOT / "reports" / "phase2").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports" / "phase2" / f"rereview_{args.split}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
