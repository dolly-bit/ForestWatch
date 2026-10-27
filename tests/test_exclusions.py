import csv
import sys
import tempfile
import types
from pathlib import Path
import numpy as np

from forestwatch.change.exclusions import exclusion_mask
from forestwatch.review import rescore_with_exclusions
from forestwatch.synthetic import make_scene_pair
from forestwatch.config import load_config
from forestwatch.pipeline import run_pipeline
from test_phase2 import _write_fake_stacks, TRANSFORM

ROOT = Path(__file__).resolve().parents[1]
CRS = "EPSG:32643"


def _stub_pyproj():
    """Invertible fake projection so the lon/lat code paths run without pyproj."""
    class T:
        @staticmethod
        def from_crs(src, dst, always_xy=True):
            class X:
                def transform(self, a, b):
                    if src == "EPSG:4326":
                        return 500000 + (a - 77.0) * 1e5, 2999000 + (b - 28.0) * 1e5
                    return 77.0 + (a - 500000) / 1e5, 28.0 + (b - 2999000) / 1e5
            return X()
    m = types.ModuleType("pyproj"); m.Transformer = T
    return m


def test_landcover_class_is_excluded_and_missing_file_is_an_error():
    cfg = {"exclusions": {"landcover_file": "lc.npy", "exclude_classes": [40]}}
    meta = {"transform": list(TRANSFORM), "crs": CRS}
    with tempfile.TemporaryDirectory() as tmp:
        try:
            exclusion_mask(cfg, tmp, meta, (20, 20)); assert False
        except FileNotFoundError:
            pass
        lc = np.full((20, 20), 10, "uint8"); lc[:, 10:] = 40
        np.save(Path(tmp) / "lc.npy", lc)
        m = exclusion_mask(cfg, tmp, meta, (20, 20))
        assert m[:, 10:].all() and not m[:, :10].any()
        try:
            exclusion_mask(cfg, tmp, meta, (30, 30)); assert False
        except ValueError:
            pass
    assert not exclusion_mask({}, ".", meta, (5, 5)).any()


def test_box_exclusion_and_pipeline_drops_detections_inside_it():
    saved = sys.modules.get("pyproj"); sys.modules["pyproj"] = _stub_pyproj()
    try:
        scene = make_scene_pair(256, 256, seed=3, season_dip=0.0, cloud_blobs=2)
        with tempfile.TemporaryDirectory() as tmp:
            _write_fake_stacks(tmp, scene)
            cfg = load_config(ROOT / "configs" / "aravalli.yaml"); cfg["region"]["output_crs"] = CRS
            base = run_pipeline(cfg, tmp, "baseline")["mask"]
            # box covering the left half of the grid: x 500000..501280 -> lon 77.0..77.0128
            cfg["exclusions"] = {"exclude_boxes": [[76.99, 27.0, 77.0128, 29.0]]}
            masked = run_pipeline(cfg, tmp, "baseline")["mask"]
            assert base[:, :128].sum() > 0 and masked[:, :120].sum() == 0
            assert masked[:, 140:].sum() > 0.9 * base[:, 140:].sum()      # right half unaffected
    finally:
        if saved is None:
            sys.modules.pop("pyproj", None)
        else:
            sys.modules["pyproj"] = saved


def test_rescore_drops_rows_inside_mask():
    saved = sys.modules.get("pyproj"); sys.modules["pyproj"] = _stub_pyproj()
    try:
        excluded = np.zeros((100, 100), bool); excluded[:, 50:] = True
        # col = (x - 500000)/10 ; x = 500000 + (lon-77)*1e5  ->  lon = 77 + col*1e-4
        rows = [("1", 77.0 + 10e-4, "y"), ("2", 77.0 + 20e-4, "n"), ("3", 77.0 + 70e-4, "n"), ("4", 77.0 + 80e-4, "n")]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "r.csv"
            with open(p, "w", newline="") as f:
                w = csv.writer(f); w.writerow(["id", "lat", "lon", "verdict"])
                for i, lon, v in rows:
                    w.writerow([i, 28.005, lon, v])      # y = 2999000 + 0.005*1e5 = 2999500 -> row 50
            r = rescore_with_exclusions(p, excluded, TRANSFORM, CRS)
        assert r["before_mask"]["n"] == 4 and r["after_mask"]["n"] == 2
        assert r["after_mask"]["real"] == 1 and r["dropped_by_mask"] == {"n": 2, "real": 0, "not_real": 2}
    finally:
        if saved is None:
            sys.modules.pop("pyproj", None)
        else:
            sys.modules["pyproj"] = saved
