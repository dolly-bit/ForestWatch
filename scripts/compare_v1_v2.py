"""How consistent were your two labelling passes (first review vs blind second look)?
Reports agreement, Cohen's kappa and the rows that changed. Needs data/labels/review_v2.csv (merge_readjudication.py)."""
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.review_summary import read_review_csv
from forestwatch.readjudication import compare_passes

ROOT = Path(__file__).resolve().parents[1]
rows, _ = read_review_csv(ROOT / "data" / "labels" / "review_v2.csv")
r = compare_passes(rows)
t = r["table"]
print(f"Rows decided (y/n) in BOTH passes: {r['n_both_decided']} (skipped because of '?' or blank: {r['skipped_unsure_or_blank']})")
print("                    second pass y   second pass n")
print(f"first pass y        {t['first_y_second_y']:13d}   {t['first_y_second_n']:13d}")
print(f"first pass n        {t['first_n_second_y']:13d}   {t['first_n_second_n']:13d}")
if r["n_both_decided"]:
    k = "undefined" if r["kappa"] is None else f"{r['kappa']:.2f}"
    print(f"Agreement: {r['agreement']:.1%}   Cohen's kappa: {k}  (1 = perfect, 0 = no better than chance)")
print("\nRows where the passes disagree, by what you wrote in the second pass:")
for (ct, lc), n in Counter((d["change_type"], d["landcover"]) for d in r["disagreements"]).most_common():
    print(f"  {n:3d}  change_type={ct or '(blank)'}  landcover={lc or '(unknown)'}")
out = ROOT / "reports" / "phase1" / "v1_vs_v2.json"
out.write_text(json.dumps(r, indent=2))
print("\nSaved", out)
