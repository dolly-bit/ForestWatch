import csv
import sys
import tempfile
from pathlib import Path
import numpy as np

from forestwatch.radar import (to_db, clean_linear, mosaic, composite_db, choose_track, local_contrast,
                               auc, auc_ci, radar_table)
from test_exclusions import _stub_pyproj, TRANSFORM, CRS


def test_db_and_cleaning():
    assert np.isclose(to_db(np.array([0.1]))[0], -10.0, atol=1e-5)
    c = clean_linear(np.array([-32768.0, 0.0, np.nan, 0.5]))
    assert np.isnan(c[:3]).all() and c[3] == 0.5
    assert np.isnan(to_db(np.array([0.0, -1.0]))).all()


def test_mosaic_and_composite():
    a = np.array([[1.0, np.nan]], "float32"); b = np.array([[9.0, 2.0]], "float32")
    assert mosaic([a, b]).tolist() == [[1.0, 2.0]]
    series = np.stack([np.full((2, 2), 0.1), np.full((2, 2), 0.1), np.full((2, 2), 10.0)]).astype("float32")
    assert np.allclose(composite_db(series), -10.0, atol=1e-4)            # median ignores the speckle outlier


def test_choose_track():
    best, n = choose_track({(1, "asc"): 5, (2, "desc"): 3}, {(1, "asc"): 1, (2, "desc"): 4})
    assert best == (2, "desc") and n == 3
    assert choose_track({(1, "asc"): 5}, {(2, "asc"): 5}) == (None, 0)


def test_local_contrast_removes_regional_shift_and_finds_patch():
    d = np.full((100, 100), 1.0, "float32")           # regional +1 dB shift everywhere
    d[48:53, 48:53] = -3.0                            # the patch fell 4 dB below its surroundings
    assert abs(local_contrast(d, 50, 50, r_in=2) - (-4.0)) < 1e-4      # 5x5 window = exactly the patch
    assert abs(local_contrast(np.full((100, 100), 2.0, "float32"), 50, 50)) < 1e-6
    assert np.isnan(local_contrast(d, 500, 500))


def test_auc_known_values():
    assert abs(auc([3, 4, 5], [1, 2, 3]) - 8.5 / 9) < 1e-9
    assert auc([1, 2], [3, 4]) == 0.0 and auc([5, 6], [1, 2]) == 1.0
    lo, hi = auc_ci([3, 4, 5, 6], [1, 2, 3, 2], n_boot=200)
    assert 0 <= lo <= hi <= 1


def test_radar_table_uses_pixel_under_each_row():
    saved = sys.modules.get("pyproj"); sys.modules["pyproj"] = _stub_pyproj()
    try:
        dvh = np.zeros((100, 100), "float32"); dvh[45:56, 20:31] = -4.0        # patch around col 25, row 50
        with tempfile.TemporaryDirectory() as tmp:
            rows = [{"id": "1", "lat": "28.005", "lon": str(77.0 + 25e-4), "verdict": "y", "area_ha": "0.5"},
                    {"id": "2", "lat": "28.005", "lon": str(77.0 + 75e-4), "verdict": "n", "area_ha": "0.5"},
                    {"id": "3", "lat": "28.005", "lon": str(77.0 + 80e-4), "verdict": "?", "area_ha": "0.5"}]
            t = radar_table(rows, dvh, dvh, TRANSFORM, CRS, r_in=2, r_out=25)
        assert [r["verdict"] for r in t] == ["y", "n"]
        assert t[0]["dvh_rel_db"] < -3.5 and abs(t[1]["dvh_rel_db"]) < 0.5
    finally:
        if saved is None:
            sys.modules.pop("pyproj", None)
        else:
            sys.modules["pyproj"] = saved
