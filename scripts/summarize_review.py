"""Candidate-level review statistics from review.csv (validated, reproducible, with uncertainty).

  python scripts/summarize_review.py
  python scripts/summarize_review.py --input outputs/review/review.csv --out-dir reports/phase1
  python scripts/summarize_review.py --init-annotations data/labels/review_annotations.csv

Writes review_summary.json and review_summary.md. Exit code 2 if the input is invalid.
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import json
from forestwatch.review_summary import (ReviewInputError, read_review_csv, summarize, render_markdown,
                                        dumps_json, sha256_of, init_annotations)

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--input", default=str(ROOT / "outputs" / "review" / "review.csv"))
ap.add_argument("--out-dir", default=str(ROOT / "reports" / "phase1"))
ap.add_argument("--meta", default=None, help="review_meta.json (default: next to the input file, if present)")
ap.add_argument("--population-size", type=int, default=None, help="size of the sampling frame, if known")
ap.add_argument("--group-by", default="kept_by_seasonal")
ap.add_argument("--verdict-column", default="verdict", help="column holding the verdicts to summarise (e.g. verdict_v2)")
ap.add_argument("--stamp", action="store_true", help="add a generated_at time (makes output non-reproducible byte-for-byte)")
ap.add_argument("--init-annotations", default=None, metavar="PATH", help="also create an audit-trail template at PATH")
args = ap.parse_args()

try:
    rows, cols = read_review_csv(args.input)
except ReviewInputError as e:
    sys.exit(f"ERROR: {e}")
if args.verdict_column != "verdict":
    if args.verdict_column not in cols:
        sys.exit(f"ERROR: column '{args.verdict_column}' not found in {args.input}")
    rows = [{**r, "verdict": r.get(args.verdict_column, "")} for r in rows]
    if "verdict" not in cols:
        cols.append("verdict")
meta_path = Path(args.meta) if args.meta else Path(args.input).with_name("review_meta.json")
meta = json.loads(meta_path.read_text()) if meta_path.exists() else None
summary = summarize(rows, cols, meta, args.population_size, args.group_by, args.input,
                    sha256_of(args.input))
if args.stamp:
    summary["generated_at"] = datetime.now(timezone.utc).isoformat()
out = Path(args.out_dir)
out.mkdir(parents=True, exist_ok=True)
(out / "review_summary.json").write_text(dumps_json(summary), encoding="utf-8")
(out / "review_summary.md").write_text(render_markdown(summary), encoding="utf-8")
print(f"Wrote {out / 'review_summary.md'} and review_summary.json")
for w in summary["validation"]["warnings"]:
    print("WARNING:", w)
if summary["validation"]["errors"]:
    print("ERRORS:", *summary["validation"]["errors"], sep="\n  ")
    sys.exit(2)
o = summary["overall"]
rate = "undefined" if o["positive_rate_among_decided"] is None else f"{o['positive_rate_among_decided']:.1%}"
print(f"y={o['y']} n={o['n']} ?={o['unsure']} unreviewed={o['unreviewed']} | positive-verdict rate among decided: {rate}")
if args.init_annotations:
    try:
        print(f"Created annotation template with {init_annotations(rows, args.init_annotations)} rows: {args.init_annotations}")
    except FileExistsError as e:
        print("Skipped:", e)
