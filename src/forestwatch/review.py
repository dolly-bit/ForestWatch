"""Visual review without GIS software.

build_review(): picks a random sample of detected candidates and draws numbered
before / after / outlined pictures plus a CSV to fill in (y = real clearing, n = not, ? = unsure).
score_review(): turns the filled CSV into precision with a 95% confidence interval, for all
candidates and for those kept / removed by the seasonal filter.

This estimates PRECISION only (how many detections are real). It cannot measure recall.
"""
from __future__ import annotations
import csv
import json
import math
from pathlib import Path
import numpy as np
from scipy import ndimage

from .pipeline import run_pipeline

EIGHT = np.ones((3, 3), dtype=int)
COLUMNS = ["id", "area_ha", "mean_ndvi_drop", "kept_by_seasonal", "lat", "lon", "maps_link", "page", "verdict"]


def _stretch01(a, lo=2, hi=98):
    finite = np.isfinite(a)
    if not finite.any():
        return np.zeros(a.shape, "float32")
    l, h = np.percentile(a[finite], [lo, hi])
    h = max(h, l + 1e-6)
    return np.where(finite, np.clip((a - l) / (h - l), 0, 1), 0).astype("float32")


def false_color(w: dict) -> np.ndarray:
    """R = NIR, G = red, B = SWIR2: vegetation looks red/pink, bare ground blue-grey."""
    return np.dstack([_stretch01(w["nir"]), _stretch01(w["red"]), _stretch01(w["swir22"])])


def wilson_ci(k: int, n: int, z: float = 1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def _lonlat(x: float, y: float, crs: str):
    """Map coordinates -> (lat, lon) or (None, None) if pyproj is unavailable."""
    try:
        from pyproj import Transformer
    except ImportError:
        return None, None
    lon, lat = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform(x, y)
    return round(float(lat), 6), round(float(lon), 6)


def overview_figure(fcb, fca, mask, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(18, 6.5))
    ax[0].imshow(fcb); ax[0].set_title("Before (false colour)")
    ax[1].imshow(fca); ax[1].set_title("After (false colour)")
    ax[2].imshow(fca)
    overlay = np.zeros(mask.shape + (4,), dtype="float32"); overlay[mask] = (1, 1, 0, 0.9)
    ax[2].imshow(overlay); ax[2].set_title(f"Detected vegetation loss (yellow): {int(ndimage.label(mask, EIGHT)[1])} areas")
    for a in ax:
        a.axis("off")
    plt.tight_layout(); plt.savefig(out_path, dpi=110); plt.close(fig)


def build_review(cfg, root, out_dir, method="baseline", n=60, seed=0, per_page=5, margin=40,
                 min_area_ha=0.0) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    all_res = run_pipeline(cfg, root, method, seasonal=False, return_windows=True)
    kept_mask = run_pipeline(cfg, root, method, seasonal=True)["mask"]
    before, after = all_res["windows"]
    mask, meta_geo = all_res["mask"], all_res["meta"]
    res_m = cfg["region"]["resolution_m"]

    labeled, n_comp = ndimage.label(mask, structure=EIGHT)
    if n_comp == 0:
        raise ValueError("No candidate areas found. Check your date windows and thresholds in the config.")
    slices = ndimage.find_objects(labeled)
    sizes = ndimage.sum(mask, labeled, index=np.arange(1, n_comp + 1))
    eligible = np.arange(1, n_comp + 1)[sizes * res_m ** 2 / 10000.0 >= min_area_ha]
    if len(eligible) == 0:
        raise ValueError(f"No candidates of at least {min_area_ha} ha. Lower --min-area-ha.")
    rng = np.random.default_rng(seed)
    chosen = np.sort(rng.choice(eligible, size=min(n, len(eligible)), replace=False))

    nd_b, nd_a = before["ndvi"], after["ndvi"]
    drop = nd_b - nd_a
    a_, b_, c_, d_, e_, f_ = meta_geo["transform"]
    H, W = mask.shape
    rows, items = [], []
    for k, cid in enumerate(chosen):
        sl = slices[cid - 1]
        comp = labeled[sl] == cid
        n_px = int(comp.sum())
        kept = float((kept_mask[sl] & comp).sum()) / n_px >= 0.5
        rr, cc = np.nonzero(comp)
        col, row_ = sl[1].start + cc.mean(), sl[0].start + rr.mean()
        lat, lon = _lonlat(c_ + a_ * (col + 0.5), f_ + e_ * (row_ + 0.5), meta_geo["crs"])
        link = f"https://www.google.com/maps?q={lat},{lon}&t=k&z=18" if lat is not None else ""
        r0, r1 = max(sl[0].start - margin, 0), min(sl[0].stop + margin, H)
        c0, c1 = max(sl[1].start - margin, 0), min(sl[1].stop + margin, W)
        page = k // per_page + 1
        row = {"id": int(cid), "area_ha": round(n_px * res_m ** 2 / 10000.0, 3),
               "mean_ndvi_drop": round(float(np.nanmean(drop[sl][comp])), 3),
               "kept_by_seasonal": "yes" if kept else "no",
               "lat": "" if lat is None else lat, "lon": "" if lon is None else lon,
               "maps_link": link, "page": page, "verdict": ""}
        rows.append(row)
        items.append((cid, (r0, r1, c0, c1), row,
                      float(np.nanmean(nd_b[sl][comp])), float(np.nanmean(nd_a[sl][comp]))))

    cmap = matplotlib.colormaps["RdYlGn"].with_extremes(bad="#cccccc")
    show_b, show_a = np.ma.masked_invalid(nd_b), np.ma.masked_invalid(nd_a)
    n_pages = math.ceil(len(items) / per_page)
    for p in range(n_pages):
        chunk = items[p * per_page:(p + 1) * per_page]
        fig, axes = plt.subplots(len(chunk), 3, figsize=(11, 3.5 * len(chunk)), squeeze=False)
        for i, (cid, (r0, r1, c0, c1), row, mb, ma) in enumerate(chunk):
            cm = (labeled[r0:r1, c0:c1] == cid).astype(float)
            for j, (img, title) in enumerate(((show_b, "before"), (show_a, "after"), (show_a, "after + outline"))):
                ax = axes[i, j]
                ax.imshow(img[r0:r1, c0:c1], cmap=cmap, vmin=0.0, vmax=0.8); ax.axis("off")
                if j == 2:
                    ax.contour(cm, levels=[0.5], colors="black", linewidths=1.6)
                ax.set_title(title if j else
                             f"#{cid} | {row['area_ha']:.2f} ha | greenness {mb:.2f} -> {ma:.2f} | "
                             f"seasonal filter: {'KEPT' if row['kept_by_seasonal'] == 'yes' else 'removed'}\nbefore",
                             fontsize=9, loc="left")
        fig.text(0.5, 0.995, "Green = vegetation | yellow/orange = sparse or bare ground | grey = no data. "
                 "Confirm with the maps_link in review.csv (satellite photo).",
                 ha="center", va="top", fontsize=9)
        plt.tight_layout(rect=[0, 0, 1, 0.975]); plt.savefig(out_dir / f"review_page_{p + 1:02d}.png", dpi=90)
        plt.close(fig)

    with open(out_dir / "review.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS); w.writeheader(); w.writerows(rows)
    overview_figure(false_color(before), false_color(after), kept_mask, out_dir / "overview.png")
    meta = {"method": method, "total_candidates": int(n_comp), "eligible": int(len(eligible)),
            "min_area_ha": min_area_ha, "sampled": len(chosen), "seed": seed,
            "kept_by_seasonal_total": int(ndimage.label(kept_mask, EIGHT)[1]), "pages": n_pages}
    (out_dir / "review_meta.json").write_text(json.dumps(meta, indent=2))
    return meta


def normalize_verdict(v) -> str:
    """Map what a person typed to 'y', 'n', '?' or '' (not reviewed / unrecognised)."""
    v = (v or "").strip().lower()
    if v in ("y", "yes", "true", "1"):
        return "y"
    if v in ("n", "no", "false", "0"):
        return "n"
    if v in ("?", "u", "unsure", "maybe"):
        return "?"
    return ""


def _precision(rows):
    k = sum(normalize_verdict(r["verdict"]) == "y" for r in rows)
    n = len(rows)
    lo, hi = wilson_ci(k, n)
    return {"n": n, "real": k, "precision": (k / n) if n else float("nan"), "ci95": [lo, hi]}


def score_review(csv_path) -> dict:
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    verdict = lambda r: normalize_verdict(r.get("verdict"))
    judged = [r for r in rows if verdict(r) in ("y", "n")]
    return {"all_candidates": _precision(judged),
            "kept_by_seasonal": _precision([r for r in judged if r["kept_by_seasonal"] == "yes"]),
            "removed_by_seasonal": _precision([r for r in judged if r["kept_by_seasonal"] == "no"]),
            "unsure": sum(verdict(r) == "?" for r in rows),
            "not_reviewed": sum(verdict(r) == "" for r in rows)}


def rescore_with_exclusions(csv_path, excluded: np.ndarray, transform, crs) -> dict:
    """Re-score an ALREADY reviewed sheet as if the exclusion mask had been applied.

    Candidates whose centre falls inside `excluded` are dropped. NOTE: if the mask was designed after
    looking at these same rows, the new precision is optimistic. Review a fresh sample for an unbiased number.
    """
    from .change.exclusions import lonlat_to_rowcol
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    H, W = excluded.shape
    kept, dropped = [], []
    for r in rows:
        if normalize_verdict(r.get("verdict")) not in ("y", "n") or not r.get("lat"):
            continue
        row, col = lonlat_to_rowcol(float(r["lon"]), float(r["lat"]), transform, crs)
        inside = 0 <= row < H and 0 <= col < W and bool(excluded[row, col])
        (dropped if inside else kept).append(r)
    return {"before_mask": _precision(kept + dropped), "after_mask": _precision(kept),
            "dropped_by_mask": {"n": len(dropped),
                                "real": sum(normalize_verdict(r["verdict"]) == "y" for r in dropped),
                                "not_real": sum(normalize_verdict(r["verdict"]) == "n" for r in dropped)}}


def landcover_breakdown(csv_path, grid: np.ndarray, transform, crs) -> dict:
    """For every judged row, look up the land-cover class under its centre.
    Returns {class: {"n", "real", "not_real"}}; class -1 means outside the grid."""
    from .change.exclusions import lonlat_to_rowcol
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    H, W = grid.shape
    out: dict = {}
    for r in rows:
        v = normalize_verdict(r.get("verdict"))
        if v not in ("y", "n") or not r.get("lat"):
            continue
        row, col = lonlat_to_rowcol(float(r["lon"]), float(r["lat"]), transform, crs)
        cls = int(grid[row, col]) if (0 <= row < H and 0 <= col < W) else -1
        d = out.setdefault(cls, {"n": 0, "real": 0, "not_real": 0})
        d["n"] += 1
        d["real" if v == "y" else "not_real"] += 1
    return out
