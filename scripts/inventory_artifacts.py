"""Write reports/phase1/artifact_inventory.csv (only verifiable fields are filled).
  python scripts/inventory_artifacts.py --run-id baseline-audit-1"""
import argparse, csv, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.audit import inventory_rows

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--run-id", required=True)
ap.add_argument("--out", default=str(ROOT / "reports" / "phase1" / "artifact_inventory.csv"))
args = ap.parse_args()
rows = inventory_rows(ROOT, args.run_id)
cols = ["artifact_path", "artifact_type", "run_id", "crs", "width", "height", "resolution", "nodata", "source_dates", "notes"]
Path(args.out).parent.mkdir(parents=True, exist_ok=True)
with open(args.out, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
print(f"Wrote {len(rows)} rows to {args.out}")
