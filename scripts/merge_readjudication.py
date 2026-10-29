"""Check your filled readjudication.csv and merge it with the original sheet + land cover -> data/labels/review_v2.csv

Then summarise it:
  python scripts/summarize_review.py --input data/labels/review_v2.csv --verdict-column verdict_v2 \
         --group-by landcover_name --meta outputs/review/review_meta.json --out-dir reports/phase1/v2
  python scripts/summarize_review.py --input data/labels/review_v2.csv --verdict-column verdict_v2 \
         --group-by change_type --meta outputs/review/review_meta.json --out-dir reports/phase1/v2_by_change_type
"""
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from forestwatch.review_summary import read_review_csv
from forestwatch.readjudication import validate_sheet, merge, write_csv
from forestwatch.landcover_diag import landcover_for_rows, CLASS_NAMES

ROOT = Path(__file__).resolve().parents[1]
orig_path = ROOT / "data" / "labels" / "review_v1_original.csv"
orig, _ = read_review_csv(orig_path if orig_path.exists() else ROOT / "outputs" / "review" / "review.csv")
sheet, _ = read_review_csv(ROOT / "data" / "labels" / "readjudication.csv")
v = validate_sheet(sheet)
for w in v["warnings"]:
    print("WARNING:", w)
classes = None
grid_path = ROOT / "data" / "landcover" / "landcover_grid.npy"
if grid_path.exists():
    meta = json.loads(sorted((ROOT / "data" / "stacks" / "after").glob("*.json"))[0].read_text())
    classes = landcover_for_rows(orig, np.load(grid_path), tuple(meta["transform"]), meta["crs"])
else:
    print("NOTE: no data/landcover/landcover_grid.npy: land-cover columns skipped")
merged, columns = merge(orig, sheet, classes, CLASS_NAMES)
out = ROOT / "data" / "labels" / "review_v2.csv"
write_csv(out, merged, columns, overwrite=True)
print(f"Wrote {len(merged)} rows to {out}")
print("change_type counts:", dict(Counter(r["change_type"] or "(blank)" for r in merged)))
