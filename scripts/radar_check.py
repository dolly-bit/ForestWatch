"""STEP 3 - do your REAL detections (y) show a different radar change than your FALSE ones (n)?"""
import csv, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from forestwatch.radar import radar_table, auc, auc_ci

ROOT = Path(__file__).resolve().parents[1]
z = np.load(ROOT / "data" / "radar" / "radar.npz")
meta = json.loads(sorted((ROOT / "data" / "stacks" / "after").glob("*.json"))[0].read_text())
rows = list(csv.DictReader(open(ROOT / "outputs" / "review" / "review.csv", newline="", encoding="utf-8-sig")))
tab = radar_table(rows, z["vh_after_db"] - z["vh_before_db"], z["vv_after_db"] - z["vv_before_db"],
                  tuple(meta["transform"]), meta["crs"])
(ROOT / "outputs").mkdir(exist_ok=True)
with open(ROOT / "outputs" / "radar_check.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(tab[0].keys())); w.writeheader(); w.writerows(tab)

print("Radar change inside each detection minus its surroundings (dB; negative = backscatter fell more than nearby)")
for key, label in (("dvh_rel_db", "VH"), ("dvv_rel_db", "VV")):
    y = np.array([r[key] for r in tab if r["verdict"] == "y"], float); y = y[np.isfinite(y)]
    n = np.array([r[key] for r in tab if r["verdict"] == "n"], float); n = n[np.isfinite(n)]
    if len(y) < 3 or len(n) < 3:
        print(f"{label}: not enough usable rows (real {len(y)}, not real {len(n)})"); continue
    score_y, score_n = -y, -n          # bigger = larger backscatter DROP
    lo, hi = auc_ci(score_y, score_n)
    print(f"{label}: real (n={len(y)}) median {np.median(y):+.2f} dB | not real (n={len(n)}) median {np.median(n):+.2f} dB"
          f" | AUC {auc(score_y, score_n):.2f}  95% CI [{lo:.2f}, {hi:.2f}]   (0.50 = no separation)")
try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(9, 4))
    for a, (key, label) in zip(ax, (("dvh_rel_db", "VH"), ("dvv_rel_db", "VV"))):
        data = [[r[key] for r in tab if r["verdict"] == v and np.isfinite(r[key])] for v in ("y", "n")]
        a.boxplot(data, labels=["real (y)", "not real (n)"]); a.axhline(0, color="grey", lw=0.8)
        a.set_title(f"{label} change vs surroundings (dB)")
    plt.tight_layout(); plt.savefig(ROOT / "outputs" / "radar_check.png", dpi=110)
    print("Saved outputs/radar_check.csv and outputs/radar_check.png")
except Exception as e:
    print("Plot skipped:", e)
