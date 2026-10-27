import csv
import tempfile
from pathlib import Path
import numpy as np
from forestwatch.review import wilson_ci, score_review, build_review
from forestwatch.synthetic import make_scene_pair
from forestwatch.config import load_config
from test_phase2 import _write_fake_stacks

ROOT = Path(__file__).resolve().parents[1]


def test_wilson_known_value():
    lo, hi = wilson_ci(8, 10)
    assert abs(lo - 0.490) < 0.005 and abs(hi - 0.943) < 0.005
    assert np.isnan(wilson_ci(0, 0)[0])


def test_review_roundtrip_on_fake_stacks():
    scene = make_scene_pair(256, 256, seed=3, season_dip=0.0, cloud_blobs=2)
    with tempfile.TemporaryDirectory() as tmp:
        _write_fake_stacks(tmp, scene)
        cfg = load_config(ROOT / "configs" / "aravalli.yaml")
        cfg["region"]["output_crs"] = "EPSG:32643"
        out = Path(tmp) / "review"
        meta = build_review(cfg, tmp, out, n=12, seed=1, per_page=4)
        assert meta["sampled"] > 0 and (out / "review_page_01.png").exists() and (out / "overview.png").exists()
        rows = list(csv.DictReader(open(out / "review.csv", newline="")))
        assert len(rows) == meta["sampled"] and rows[0]["verdict"] == ""
        for i, r in enumerate(rows):                       # simulate a reviewer: all real except one 'n' and one '?'
            r["verdict"] = "n" if i == 0 else "?" if i == 1 else "y"
        with open(out / "review.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        s = score_review(out / "review.csv")
        assert s["all_candidates"]["n"] == len(rows) - 1 and s["unsure"] == 1
        assert s["all_candidates"]["real"] == len(rows) - 2


def test_min_area_filter_and_link_columns():
    scene = make_scene_pair(256, 256, seed=3, season_dip=0.0, cloud_blobs=2)
    with tempfile.TemporaryDirectory() as tmp:
        _write_fake_stacks(tmp, scene)
        cfg = load_config(ROOT / "configs" / "aravalli.yaml")
        cfg["region"]["output_crs"] = "EPSG:32643"
        out = Path(tmp) / "review"
        build_review(cfg, tmp, out, n=5, seed=1, min_area_ha=0.0)
        row = next(csv.DictReader(open(out / "review.csv", newline="")))
        assert {"lat", "lon", "maps_link", "verdict"} <= set(row.keys())
        try:
            build_review(cfg, tmp, out, n=5, min_area_ha=10_000.0); assert False
        except ValueError:
            pass
