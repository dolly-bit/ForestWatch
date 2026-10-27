"""Re-score your finished review.csv as if the exclusions in the config had been applied.
Optimistic if the exclusions were chosen after seeing these rows: say so in your report."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.config import load_config
from forestwatch.change.exclusions import exclusion_mask
from forestwatch.review import rescore_with_exclusions

ROOT = Path(__file__).resolve().parents[1]
cfg = load_config(ROOT / "configs" / "aravalli.yaml")
meta = json.loads(sorted((ROOT / "data" / "stacks" / "after").glob("*.json"))[0].read_text())
excluded = exclusion_mask(cfg, ROOT, meta, (meta["height"], meta["width"]))
print(f"Excluded {excluded.mean():.1%} of the area")
r = rescore_with_exclusions(ROOT / "outputs" / "review" / "review.csv", excluded, tuple(meta["transform"]), meta["crs"])
for k in ("before_mask", "after_mask"):
    x = r[k]
    print(f"{k:12s} judged {x['n']:3d} real {x['real']:3d} precision {x['precision']:.2f} CI [{x['ci95'][0]:.2f}, {x['ci95'][1]:.2f}]")
print("dropped by the mask:", r["dropped_by_mask"])
