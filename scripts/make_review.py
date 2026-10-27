"""Make numbered before/after pictures of detected areas + a CSV to fill in. No QGIS needed.

  python scripts/make_review.py              # 60 random candidates, 5 per page
  python scripts/make_review.py --n 40
Then open outputs/review/review_page_01.png ... and fill the 'verdict' column of outputs/review/review.csv
(y = real vegetation clearing, n = not, ? = unsure). Finally run scripts/score_review.py.
"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.config import load_config
from forestwatch.review import build_review

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=60)
ap.add_argument("--method", choices=["baseline", "unet"], default="baseline")
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--min-area-ha", type=float, default=0.3, help="only review candidates at least this big (easier to see)")
args = ap.parse_args()
cfg = load_config(ROOT / "configs" / "aravalli.yaml")
meta = build_review(cfg, ROOT, ROOT / "outputs" / "review", args.method, args.n, args.seed, min_area_ha=args.min_area_ha)
print(meta)
print("Check each one: click its maps_link in review.csv (satellite photo), compare with the picture.")
print("Next: open outputs/review/review_page_01.png, then fill the 'verdict' column in outputs/review/review.csv")
print("(y = real clearing, n = not a clearing, ? = unsure). Overview picture: outputs/review/overview.png")
