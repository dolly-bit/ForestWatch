"""Merge your filled label sheet with the hidden sampling information -> data/reference/labels_<split>.csv + .geojson.
  python scripts/ingest_labels.py --split validation"""
import argparse, json, sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.reference.context import load_context
from forestwatch.reference.schema import read_rows, write_rows, LABEL_COLUMNS, SPLITS
from forestwatch.reference.labels import merge_labels
from forestwatch.reference.export import labels_geojson

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--split", required=True, choices=SPLITS)
ap.add_argument("--allow-partial", action="store_true", help="accept a sheet that is not completely filled in")
ap.add_argument("--force", action="store_true")
args = ap.parse_args()
cfg, ref, meta, shape = load_context(ROOT)
d = ROOT / "data" / "reference"
sheet = read_rows(d / f"label_sheet_{args.split}.csv")
selected = read_rows(d / f"selected_units_{args.split}.csv")
labels, unlabelled = merge_labels(sheet, selected, ref, date.today().isoformat(), meta["crs"])
if unlabelled and not args.allow_partial:
    sys.exit(f"{len(unlabelled)} chip(s) still have no class_label (e.g. {unlabelled[:5]}). Finish the sheet or use --allow-partial.")
labels.sort(key=lambda r: r["unit_id"])
write_rows(d / f"labels_{args.split}.csv", labels, LABEL_COLUMNS, args.force)
gj = labels_geojson(labels, tuple(meta["transform"]), meta["crs"], LABEL_COLUMNS)
(d / f"labels_{args.split}.geojson").write_text(json.dumps(gj), encoding="utf-8")
print(f"Wrote {len(labels)} labels to data/reference/labels_{args.split}.csv (+ .geojson). Unlabelled skipped: {len(unlabelled)}")
