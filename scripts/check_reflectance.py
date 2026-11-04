"""Is the reflectance scaling right?  (Your NDVI table showed a median NDVI of 1.00 for tree cover and shrubland,
which real vegetation almost never has. A common cause: the +1000 DN offset subtracted from data that does not
carry it, which clips dark red values to exactly 0 and pushes NDVI to 1.)

  python scripts/check_reflectance.py
Prints, per stack, how many valid pixels have red reflectance exactly 0 and typical red / NIR / NDVI values.
Healthy vegetation: red about 0.02-0.08, NIR about 0.25-0.45, NDVI about 0.5-0.85, almost no exact zeros."""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from forestwatch.data.stack_io import load_stack
from forestwatch.preprocess.indices import ndvi
from forestwatch.audit import flag_hazy_dates

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--stacks-dir", default=str(ROOT / "data" / "stacks"), help="folder with before/ and after/ (default data/stacks)")
STACKS = Path(ap.parse_args().stacks_dir)
suspect = 0
scene_rows = []
print(f"{'window':6s} {'date':10s} {'valid':>6s} {'red==0':>7s} {'red p5/50/95':>20s} {'nir p5/50/95':>20s} {'NDVI med':>8s} {'NDVI>=.95':>9s}  scaling")
for window in ("before", "after"):
    for f in sorted((STACKS / window).glob("*.npz")):
        arr, meta = load_stack(f)
        v = arr["valid"] & (arr["red"] + arr["nir"] > 0)
        if not v.any():
            continue
        r, n = arr["red"][v], arr["nir"][v]
        nd = ndvi(arr["nir"], arr["red"])[v]
        zero = float((r == 0).mean())
        pr, pn = np.percentile(r, [5, 50, 95]), np.percentile(n, [5, 50, 95])
        flag = " <-- SUSPECT" if zero > 0.05 else ""
        suspect += zero > 0.05
        scene_rows.append({"window": window, "date": meta["date"], "valid_share": float(v.mean()),
                           "red_median": float(pr[1]), "ndvi_median": float(np.median(nd))})
        print(f"{window:6s} {meta['date']:10s} {v.mean():6.0%} {zero:7.1%} "
              f"{pr[0]:6.3f}/{pr[1]:.3f}/{pr[2]:.3f} {pn[0]:6.3f}/{pn[1]:.3f}/{pn[2]:.3f} {np.median(nd):8.2f} "
              f"{(nd >= 0.95).mean():9.1%}  {meta.get('reflectance_scaling', 'unknown (built before this check existed)')}{flag}")
for window in ("before", "after"):
    cat = ROOT / "data" / "raw" / f"catalog_{window}.json"
    if cat.exists():
        first = json.loads(cat.read_text())[0]
        print(f"\ncatalog_{window}.json says (first scene {first['id']}): raster = {first.get('raster', 'NOT RECORDED - re-run search_scenes.py')}")
print("\nPer-date summary (scenes with at least 50% clear pixels; dates that look hazy compared with the rest of their window):")
dates = flag_hazy_dates(scene_rows)
print(f"{'window':6s} {'date':10s} {'scenes':>6s} {'red med':>8s} {'NDVI med':>9s} {'vs window':>10s}")
hazy = []
for d in dates:
    mark = ""
    if d.get("hazy"):
        mark, _ = "  <-- HAZY?", hazy.append(d["date"])
    elif d.get("hazy") is None:
        mark = "  (too few dates to judge)"
    print(f"{d['window']:6s} {d['date']:10s} {d['n_scenes']:6d} {d['red_median']:8.3f} {d['ndvi_median']:9.2f} "
          f"{d.get('ndvi_vs_window', float('nan')):+10.2f}{mark}")
print()
if suspect:
    print(f"RESULT: {suspect} stack(s) have many exact-zero red values: the scaling is probably wrong.\n"
          "Back up data/stacks, then rebuild with:  python scripts/build_stacks.py --scaling none   and run this check again.")
else:
    print("RESULT: no stack has many exact-zero red values (scaling looks plausible).")
if hazy:
    print(f"Possible haze on {len(hazy)} date(s): {', '.join(hazy)}. Send me this table; we will decide whether to drop those dates.")
