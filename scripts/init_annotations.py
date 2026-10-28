"""Create the review audit-trail template data/labels/review_annotations.csv (never overwrites)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.review_summary import read_review_csv, init_annotations

ROOT = Path(__file__).resolve().parents[1]
rows, _ = read_review_csv(ROOT / "outputs" / "review" / "review.csv")
try:
    print("Created", init_annotations(rows, ROOT / "data" / "labels" / "review_annotations.csv"), "rows")
except FileExistsError as e:
    print("Skipped:", e)
