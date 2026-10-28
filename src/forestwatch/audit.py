"""Provenance helpers: git info, package versions, stack metadata, reproduction check, inventory."""
from __future__ import annotations
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
import numpy as np
from scipy import ndimage

from .eval.grids import check_same_grid, GridMismatchError

EIGHT = np.ones((3, 3), dtype=int)
PACKAGES = ("numpy", "scipy", "scikit-image", "matplotlib", "PyYAML", "rasterio", "pyproj", "pystac-client", "torch")


def sha256_file(path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def git_info(root) -> dict:
    def run(*args):
        return subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True, timeout=15)
    try:
        head = run("rev-parse", "HEAD")
        if head.returncode != 0:
            return {"available": False}
        return {"available": True, "commit": head.stdout.strip(),
                "branch": run("rev-parse", "--abbrev-ref", "HEAD").stdout.strip(),
                "uncommitted_changes": bool(run("status", "--porcelain").stdout.strip())}
    except (OSError, subprocess.SubprocessError):
        return {"available": False}


def package_versions(names=PACKAGES) -> dict:
    out = {}
    for n in names:
        try:
            out[n] = metadata.version(n)
        except metadata.PackageNotFoundError:
            out[n] = "not installed"
    return out


def stack_metas(root) -> list[dict]:
    """One entry per stack on disk (scene id, date, grid) read from the JSON beside each .npz."""
    out = []
    for window in ("before", "after"):
        for jp in sorted((Path(root) / "data" / "stacks" / window).glob("*.json")):
            m = json.loads(jp.read_text())
            npz = jp.with_suffix(".npz")
            out.append({"window": window, "file": str(jp.with_suffix(".npz").relative_to(root)).replace("\\", "/"),
                        "scene_id": m.get("scene_id"), "date": m.get("date"), "crs": m.get("crs"),
                        "width": m.get("width"), "height": m.get("height"), "transform": m.get("transform"),
                        "valid_fraction": m.get("valid_fraction"),
                        "size_bytes": npz.stat().st_size if npz.exists() else None})
    return out


def check_stacks_share_grid(metas: list[dict]) -> str:
    """'OK (n stacks)' or a description of the mismatch."""
    if not metas:
        return "no stacks found"
    try:
        for m in metas[1:]:
            check_same_grid(metas[0], m, metas[0]["file"], m["file"])
    except GridMismatchError as e:
        return f"MISMATCH: {e}"
    return f"OK ({len(metas)} stacks share one grid)"


def reproduce_review(cfg: dict, root, review_dir, method: str = "baseline", check_seasonal: bool = True) -> dict:
    """Re-run the detector and test whether it regenerates the exact candidates that were reviewed.

    Checks (each reported separately): candidate count, eligible count, the random sample (re-drawn from
    the recorded seed), the area of every reviewed candidate, and (optionally) the seasonal-filter flags.
    """
    from .pipeline import run_pipeline
    review_dir = Path(review_dir)
    with open(review_dir / "review.csv", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    meta_path = review_dir / "review_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else None
    res_m = cfg["region"]["resolution_m"]

    res = run_pipeline(cfg, root, method, seasonal=False)
    labeled, n_comp = ndimage.label(res["mask"], structure=EIGHT)
    sizes = ndimage.sum(res["mask"], labeled, index=np.arange(1, n_comp + 1)) if n_comp else np.array([])
    areas = sizes * res_m ** 2 / 10000.0
    checks = []

    def add(name, passed, detail):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    if meta is None:
        add("review_meta.json present", False, "missing: sampling frame cannot be verified, only areas below")
    else:
        add("total candidates", n_comp == meta["total_candidates"],
            f"now {n_comp}, recorded {meta['total_candidates']}")
        eligible_ids = np.arange(1, n_comp + 1)[areas >= meta.get("min_area_ha", 0.0)]
        add("eligible candidates", len(eligible_ids) == meta.get("eligible"),
            f"now {len(eligible_ids)}, recorded {meta.get('eligible')} (min area {meta.get('min_area_ha')} ha)")
        if len(eligible_ids):
            rng = np.random.default_rng(meta["seed"])
            redrawn = sorted(int(i) for i in rng.choice(eligible_ids, size=min(meta["sampled"], len(eligible_ids)),
                                                        replace=False))
            got = sorted(int(r["id"]) for r in rows)
            add("random sample re-drawn from recorded seed", redrawn == got,
                f"seed {meta['seed']}: {'identical id set' if redrawn == got else 'id sets differ'}")
    bad = []
    for r in rows:
        i = int(r["id"])
        now = round(float(areas[i - 1]), 3) if 1 <= i <= n_comp else None
        if now is None or abs(now - float(r["area_ha"])) > 1e-3:
            bad.append((i, r["area_ha"], now))
    add("area of every reviewed candidate", not bad,
        "all match" if not bad else f"{len(bad)} differ, e.g. {bad[:3]} (id, recorded, now)")

    if check_seasonal:
        kept = run_pipeline(cfg, root, method, seasonal=True)["mask"]
        slices = ndimage.find_objects(labeled)
        wrong = []
        for r in rows:
            i = int(r["id"])
            if not (1 <= i <= n_comp):
                continue
            sl = slices[i - 1]
            comp = labeled[sl] == i
            flag = "yes" if float((kept[sl] & comp).sum()) / comp.sum() >= 0.5 else "no"
            if flag != r["kept_by_seasonal"]:
                wrong.append(i)
        add("kept_by_seasonal flag of every reviewed candidate", not wrong,
            "all match" if not wrong else f"{len(wrong)} differ, ids {wrong[:5]}")

    overall = "PASS" if all(c["passed"] for c in checks) else "FAIL"
    return {"overall": overall, "checks": checks, "candidates_now": int(n_comp), "method": method}


def inventory_rows(root, run_id: str) -> list[dict]:
    """Artifact inventory; only fields that can be verified are filled."""
    root = Path(root)
    rows = []

    def row(path, typ, crs="", w="", h="", res="", nodata="", dates="", notes=""):
        rows.append({"artifact_path": str(Path(path).relative_to(root)).replace("\\", "/"), "artifact_type": typ,
                     "run_id": run_id, "crs": crs, "width": w, "height": h, "resolution": res,
                     "nodata": nodata, "source_dates": dates, "notes": notes})

    for m in stack_metas(root):
        res = abs(m["transform"][0]) if m["transform"] else ""
        row(root / m["file"], f"sentinel2_stack_{m['window']}", m["crs"], m["width"], m["height"], res,
            "NaN reflectance; boolean valid mask inside", m["date"],
            f"scene {m['scene_id']}; valid fraction {m['valid_fraction']}")
    for tif in sorted((root / "outputs" / "qgis").glob("*.tif")) if (root / "outputs" / "qgis").exists() else []:
        try:
            import rasterio
            with rasterio.open(tif) as src:
                row(tif, "geotiff_for_qgis", str(src.crs), src.width, src.height, abs(src.transform.a), src.nodata,
                    "", f"{src.count} band(s), dtype {src.dtypes[0]}")
        except ImportError:
            row(tif, "geotiff_for_qgis", notes="rasterio not installed: metadata not read")
    for rel, typ in (("outputs/review/review.csv", "review_sheet"), ("outputs/review/review_meta.json", "review_meta"),
                     ("data/landcover/landcover_grid.npy", "landcover_grid"), ("data/radar/radar.npz", "radar_composites"),
                     ("data/labels/change.npy", "label_raster"), ("configs/aravalli.yaml", "config")):
        p = root / rel
        if p.exists():
            row(p, typ, notes=f"{p.stat().st_size} bytes, sha256 {sha256_file(p)[:16]}...")
    return rows


def new_run_id(cfg_path) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"run-{stamp}-{sha256_file(cfg_path)[:8]}"


def write_run_manifest(root, cfg_path, run_id: str, extra: dict | None = None) -> Path:
    """outputs/runs/<run_id>/ with a copy of the config and manifest.json. Never overwrites an existing run."""
    root = Path(root)
    out = root / "outputs" / "runs" / run_id
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy(cfg_path, out / "config_used.yaml")
    metas = stack_metas(root)
    manifest = {"run_id": run_id, "created_utc": datetime.now(timezone.utc).isoformat(),
                "command": " ".join(sys.argv), "git": git_info(root), "packages": package_versions(),
                "python": sys.version.split()[0], "config_sha256": sha256_file(cfg_path),
                "grid_check": check_stacks_share_grid(metas),
                "scenes": [{k: m[k] for k in ("window", "scene_id", "date", "file")} for m in metas],
                "extra": extra or {}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return out
