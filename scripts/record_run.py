"""Write reports/phase1/baseline_run.md from the real config, stack metadata and git/package info.
Anything that cannot be recovered is written as 'Unknown' (never guessed).

  python scripts/record_run.py --run-id baseline-audit-1
"""
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.config import load_config
from forestwatch.audit import git_info, package_versions, stack_metas, check_stacks_share_grid, sha256_file

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--run-id", required=True, help="an ID you assign now (retrospective audit ID)")
ap.add_argument("--out", default=str(ROOT / "reports" / "phase1" / "baseline_run.md"))
args = ap.parse_args()

cfg_path = ROOT / "configs" / "aravalli.yaml"
cfg = load_config(cfg_path)
metas = stack_metas(ROOT)
git = git_info(ROOT)
review_csv = ROOT / "outputs" / "review" / "review.csv"
mtime = lambda p: datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat() if p.exists() else "missing"
repro_path = ROOT / "reports" / "phase1" / "reproduction_check.json"
repro = json.loads(repro_path.read_text()) if repro_path.exists() else None

by_window = {w: [m for m in metas if m["window"] == w] for w in ("before", "after")}
scene_lines = [f"  - {w}: " + (", ".join(f"{m['scene_id']} ({m['date']})" for m in ms) or "none found")
               for w, ms in by_window.items()]
warnings = []
if cfg_path.exists() and review_csv.exists() and cfg_path.stat().st_mtime > review_csv.stat().st_mtime:
    warnings.append("configs/aravalli.yaml was modified AFTER review.csv was created: the current config may not "
                    "be the one that produced the reviewed candidates (see reproduction check).")
if git["available"] and git["uncommitted_changes"]:
    warnings.append("The git working tree has uncommitted changes; the commit hash does not fully describe the code.")
if not git["available"]:
    warnings.append("Not a git repository (or git not installed): code version is Unknown.")
grid = check_stacks_share_grid(metas)
if not grid.startswith("OK"):
    warnings.append(f"Stack grid check: {grid}")
if repro is None:
    warnings.append("No reproduction check found. Run scripts/verify_baseline.py to test whether the reviewed "
                    "candidates can be regenerated.")
elif repro["overall"] != "PASS":
    warnings.append("Reproduction check FAILED: the reviewed sample cannot be regenerated with the current "
                    "config/data. Treat the baseline as not reproduced and record a new run ID for any new run.")

vm, cmk, bl, sea = cfg["region"], cfg["cloud_mask"], cfg["baseline"], cfg.get("seasonal", {})
lines = [
    "# Baseline run record", "",
    f"- Run ID: {args.run_id} (assigned retrospectively at audit time)",
    f"- Run date/time (with timezone): Unknown (not logged). File modification times (UTC): review.csv {mtime(review_csv)}; "
    f"config {mtime(cfg_path)}",
    f"- Git commit: {git['commit'] if git['available'] else 'Unknown (no git repository)'}"
    + (f" on branch {git['branch']}, uncommitted changes: {git['uncommitted_changes']}" if git["available"] else ""),
    "- Command executed: Unknown (not logged for the original run). The review sheet came from scripts/make_review.py "
    "(see review_meta.json for its parameters).",
    f"- Configuration file and version: configs/aravalli.yaml, sha256 {sha256_file(cfg_path)} (state at audit time)",
    f"- Study-area boundary / bbox: {vm['bbox']} (lon_min, lat_min, lon_max, lat_max, EPSG:4326)",
    f"- Before window: {cfg['windows']['before'][0]} to {cfg['windows']['before'][1]}",
    f"- After window: {cfg['windows']['after'][0]} to {cfg['windows']['after'][1]}",
    f"- STAC catalog and collection: {cfg['stac']['url']} / {cfg['stac']['collection']} "
    f"(scene-level cloud filter < {cfg['stac']['max_cloud_cover']}%)",
    "- Scene/item IDs used (from the stacks on disk; the STAC search itself was not logged):", *scene_lines,
    f"- Cloud/shadow filtering method: Sentinel-2 SCL classes {cmk['valid_scl_classes']} treated as valid, invalid areas "
    "dilated by 1 pixel (8-connected)",
    f"- Composite method: per-pixel median over clear dates in each window; at least {cmk['min_valid_observations']} "
    "clear observations required",
    f"- CRS and pixel resolution: {vm['crs']}, {vm['resolution_m']} m",
    "- NDVI formula and bands: NDVI = (NIR - Red) / (NIR + Red) using catalog asset keys 'nir' and 'red' "
    "(expected Sentinel-2 B08 and B04; verify against the catalog); reflectance scaled with the 2022 offset rule",
    f"- NDVI-drop/change threshold: drop >= {bl['ndvi_drop_min']} and pre-change NDVI >= {bl['forest_ndvi_min']}",
    f"- Seasonal persistence settings: enabled={sea.get('enabled')}, drop must appear on >= "
    f"{sea.get('min_persistence')} of clear 'after' dates, >= {sea.get('min_observations')} observations "
    "(the review sample was drawn from candidates BEFORE this filter; each candidate's kept/removed flag was computed afterwards)",
    f"- Minimum region size / area filter: {bl['min_area_pixels']} pixels (about {bl['min_area_pixels'] * vm['resolution_m'] ** 2 / 10000:.2f} ha); "
    "review sampling used its own minimum area (see review_meta.json)",
    f"- Input files: {len(metas)} stack file(s) in data/stacks/ (see artifact_inventory.csv); grid check: {grid}",
    "- Output files: outputs/review/review.csv, review_meta.json, review pages, overview.png",
    "- Software versions: " + ", ".join(f"{k} {v}" for k, v in package_versions().items()),
    "- Known warnings or manual interventions:",
    *([f"  - {w}" for w in warnings] or ["  - none detected automatically"]),
    "  - Verdicts were entered by hand; see labeling_protocol.md",
    "  - Post-hoc analyses on the same labels (farmland cluster, cropland mask, radar check) are listed in known_limitations.md",
]
if repro:
    lines.append(f"- Reproduction check: {repro['overall']} (details in reproduction_check.json)")
Path(args.out).parent.mkdir(parents=True, exist_ok=True)
Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
print("Wrote", args.out)
for w in warnings:
    print("WARNING:", w)
