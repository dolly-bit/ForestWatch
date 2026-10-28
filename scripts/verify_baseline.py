"""Does re-running the detector today reproduce the candidates you reviewed?

Checks: candidate count, eligible count, the random sample (re-drawn from the recorded seed), the area of every
reviewed candidate and its seasonal-filter flag. PASS means the reviewed sample came from exactly this
data + configuration. FAIL means something changed since the review (config, stacks or code).
Run it with the SAME configs/aravalli.yaml and stacks you used for make_review.py (and no exclusions).
Takes a few minutes (two detector runs).
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.config import load_config
from forestwatch.audit import reproduce_review

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--review-dir", default=str(ROOT / "outputs" / "review"))
ap.add_argument("--out", default=str(ROOT / "reports" / "phase1" / "reproduction_check.json"))
ap.add_argument("--skip-seasonal-check", action="store_true", help="skip the second (seasonal) run")
args = ap.parse_args()
cfg = load_config(ROOT / "configs" / "aravalli.yaml")
if cfg.get("exclusions"):
    print("NOTE: the config has an 'exclusions' section. The original review was made without it; "
          "remove it before verifying.")
res = reproduce_review(cfg, ROOT, args.review_dir, check_seasonal=not args.skip_seasonal_check)
Path(args.out).parent.mkdir(parents=True, exist_ok=True)
Path(args.out).write_text(json.dumps(res, indent=2))
for c in res["checks"]:
    print(f"[{'PASS' if c['passed'] else 'FAIL'}] {c['name']}: {c['detail']}")
print("OVERALL:", res["overall"])
sys.exit(0 if res["overall"] == "PASS" else 1)
