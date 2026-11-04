import csv
import json
import tempfile
from pathlib import Path
import numpy as np
import pytest

from forestwatch.eval.grids import check_same_grid, check_same_shape, GridMismatchError
from forestwatch.manifest import build_manifest
from forestwatch.audit import (reproduce_review, stack_metas, check_stacks_share_grid, inventory_rows, git_info,
                               new_run_id, write_run_manifest)
from forestwatch.review import build_review
from forestwatch.config import load_config
from forestwatch.synthetic import make_scene_pair
from test_phase2 import _write_fake_stacks, TRANSFORM

ROOT = Path(__file__).resolve().parents[1]
META = {"crs": "EPSG:32643", "width": 100, "height": 80, "transform": list(TRANSFORM)}


def test_grid_checks_fail_loudly():
    check_same_grid(META, dict(META))
    for key, val in (("crs", "EPSG:4326"), ("width", 101), ("transform", [20, 0, 500000, 0, -20, 3000000])):
        with pytest.raises(GridMismatchError):
            check_same_grid(META, {**META, key: val})
    check_same_shape("a", np.zeros((3, 4)), "b", np.zeros((3, 4)))
    with pytest.raises(GridMismatchError):
        check_same_shape("labels", np.zeros((3, 4)), "pred", np.zeros((4, 3)))


def test_split_manifest_is_deterministic_leak_free_and_georeferenced():
    cfg = load_config(ROOT / "configs" / "aravalli.yaml")["split"]
    meta = {"crs": "EPSG:32643", "width": 1024, "height": 1024, "transform": list(TRANSFORM)}
    a, b = build_manifest(cfg, meta, "t"), build_manifest(cfg, meta, "t")
    assert a == b and len(a) == 64
    splits = {r["split"] for r in a}
    assert {"train", "validation", "test"} <= splits and splits <= {"train", "validation", "test", "buffer"}
    first = a[0]
    assert first["min_x"] == 500000 and first["max_y"] == 3000000 and first["px_row1"] == 128
    assert first["max_x"] == 500000 + 128 * 10 and first["min_y"] == 3000000 - 128 * 10


def _setup(tmp, **cfg_changes):
    scene = make_scene_pair(256, 256, seed=3, season_dip=0.0, cloud_blobs=2)
    _write_fake_stacks(tmp, scene)
    cfg = load_config(ROOT / "configs" / "aravalli.yaml")
    cfg["region"]["output_crs"] = "EPSG:32643"
    return cfg


def test_reproduction_check_passes_then_fails_when_config_changes():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _setup(tmp)
        out = Path(tmp) / "review"
        build_review(cfg, tmp, out, n=8, seed=5, per_page=4)
        ok = reproduce_review(cfg, tmp, out)
        assert ok["overall"] == "PASS" and all(c["passed"] for c in ok["checks"]) and len(ok["checks"]) == 5
        cfg["baseline"]["ndvi_drop_min"] = 0.55                     # a different detector
        bad = reproduce_review(cfg, tmp, out)
        assert bad["overall"] == "FAIL"
        names = {c["name"] for c in bad["checks"] if not c["passed"]}
        assert "total candidates" in names and "area of every reviewed candidate" in names


def test_reproduction_detects_a_tampered_sample_and_missing_meta():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _setup(tmp)
        out = Path(tmp) / "review"
        build_review(cfg, tmp, out, n=6, seed=1, per_page=3)
        meta = json.loads((out / "review_meta.json").read_text()); meta["seed"] = 99
        (out / "review_meta.json").write_text(json.dumps(meta))
        r = reproduce_review(cfg, tmp, out, check_seasonal=False)
        assert any(c["name"].startswith("random sample") and not c["passed"] for c in r["checks"])
        (out / "review_meta.json").unlink()
        r2 = reproduce_review(cfg, tmp, out, check_seasonal=False)
        assert r2["checks"][0]["name"] == "review_meta.json present" and r2["overall"] == "FAIL"


def test_stack_metadata_inventory_and_run_manifest():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _setup(tmp)
        metas = stack_metas(tmp)
        assert len(metas) == 7 and check_stacks_share_grid(metas).startswith("OK")
        bad = [dict(m) for m in metas]; bad[3]["width"] = 999
        assert check_stacks_share_grid(bad).startswith("MISMATCH")
        rows = inventory_rows(tmp, "run-x")
        assert len(rows) == 7 and rows[0]["crs"] == "EPSG:32643" and rows[0]["run_id"] == "run-x"
        assert rows[0]["resolution"] == 10.0 and rows[0]["source_dates"]
        assert git_info(tmp)["available"] in (True, False)
        cfg_path = ROOT / "configs" / "aravalli.yaml"
        rid = new_run_id(cfg_path)
        out = write_run_manifest(tmp, cfg_path, rid, {"n": 1})
        m = json.loads((out / "manifest.json").read_text())
        assert m["run_id"] == rid and (out / "config_used.yaml").exists() and m["grid_check"].startswith("OK")
        assert len(m["scenes"]) == 7 and m["extra"] == {"n": 1}
        with pytest.raises(FileExistsError):
            write_run_manifest(tmp, cfg_path, rid)                   # runs are never overwritten


def test_hazy_date_flagging():
    from forestwatch.audit import flag_hazy_dates
    rows = []
    for k in range(8):                                               # normal dates
        rows.append({"window": "before", "date": f"2022-10-{10 + k:02d}", "valid_share": 0.99, "red_median": 0.08, "ndvi_median": 0.50})
    rows.append({"window": "before", "date": "2022-11-01", "valid_share": 0.99, "red_median": 0.16, "ndvi_median": 0.25})   # smog
    rows.append({"window": "before", "date": "2022-11-02", "valid_share": 0.20, "red_median": 0.30, "ndvi_median": 0.05})   # mostly cloud: ignored
    rows.append({"window": "after", "date": "2024-11-01", "valid_share": 0.99, "red_median": 0.30, "ndvi_median": 0.10})
    rows.append({"window": "after", "date": "2024-11-06", "valid_share": 0.99, "red_median": 0.08, "ndvi_median": 0.50})
    out = {(d["window"], d["date"]): d for d in flag_hazy_dates(rows)}
    assert out[("before", "2022-11-01")]["hazy"] is True
    assert all(out[("before", f"2022-10-{10 + k:02d}")]["hazy"] is False for k in range(8))
    assert ("before", "2022-11-02") not in out                       # too little clear imagery to judge
    assert all(d["hazy"] is None for k, d in out.items() if k[0] == "after")      # only 2 dates: cannot judge
