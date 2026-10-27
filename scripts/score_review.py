"""Turn the filled-in review.csv into precision numbers with 95% confidence intervals."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.review import score_review

ROOT = Path(__file__).resolve().parents[1]
res = score_review(ROOT / "outputs" / "review" / "review.csv")
for name in ("all_candidates", "kept_by_seasonal", "removed_by_seasonal"):
    r = res[name]
    if r["n"]:
        print(f"{name:22s} reviewed {r['n']:3d}  real {r['real']:3d}  precision {r['precision']:.2f}  "
              f"95% CI [{r['ci95'][0]:.2f}, {r['ci95'][1]:.2f}]")
    else:
        print(f"{name:22s} no reviewed rows")
print("unsure:", res["unsure"], "| not reviewed yet:", res["not_reviewed"])
(ROOT / "outputs" / "review" / "review_scores.json").write_text(json.dumps(res, indent=2))
