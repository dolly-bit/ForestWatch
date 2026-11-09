import tempfile
from pathlib import Path
import numpy as np

from forestwatch.data.stack_io import save_stack
from forestwatch.pipeline import load_window
from forestwatch.preprocess.scene_quality import (parse_scene_id, dedupe_flags, hazy_flags, select_scenes, settings, scene_stats)
from forestwatch.preprocess.indices import ndvi

TF = [10, 0, 500000, 0, -10, 3000000]


def test_scene_id_parsing_and_dedupe_keeps_the_newest_version():
    assert parse_scene_id("S2B_43RGM_20241030_1_L2A") == ("S2B_43RGM_20241030", 1)
    assert parse_scene_id("fake") == ("fake", None)
    ids = ["S2B_43RGM_20241030_0_L2A", "S2B_43RGM_20241030_1_L2A", "S2B_43RGN_20241030_0_L2A", "fake", "S2A_43RGM_20241105_0_L2A"]
    assert dedupe_flags(ids) == [False, True, True, True, True]          # other tile / other date / odd ids are never merged
    assert dedupe_flags(list(reversed(ids[:2]))) == [True, False]        # order does not matter


def _stats(valid, red, nd, n=100000):
    return {"valid_share": valid, "n_valid": n, "red_median": red, "ndvi_median": nd}


def test_hazy_flags_use_clear_scenes_as_reference_and_can_abstain():
    normal = [_stats(0.99, 0.08, 0.50) for _ in range(8)]
    stats = normal + [_stats(0.99, 0.16, 0.25), _stats(0.99, 0.08, 0.38), _stats(0.20, 0.20, 0.10, n=1000)]
    f = hazy_flags(stats, 0.10, 0.03, 0.5, 5000)
    assert f[:8] == [False] * 8 and f[8] is True and f[9] is True and f[10] is None     # tiny sample: cannot judge
    assert hazy_flags(normal[:2], 0.10, 0.03, 0.5, 5000) == [None, None]                # fewer than 3 reference scenes
    assert hazy_flags([_stats(0.99, 0.08, 0.5)] * 5 + [_stats(0.99, 0.10, 0.45)], 0.10, 0.03, 0.5, 5000)[-1] is False  # mild: not flagged


def test_select_scenes_respects_switches_and_minimum_kept():
    ids = [f"S2B_43RGM_202411{d:02d}_0_L2A" for d in range(1, 11)]
    stats = [_stats(0.99, 0.08, 0.50) for _ in range(8)] + [_stats(0.99, 0.18, 0.2)] * 2
    keep, _ = select_scenes(ids, stats, None)                                          # defaults: hazy dropping off
    assert all(keep)
    keep, dec = select_scenes(ids, stats, {"drop_hazy_scenes": True})
    assert keep == [True] * 8 + [False] * 2 and sum(1 for d in dec if not d["kept"]) == 2
    keep, dec = select_scenes(ids, stats, {"drop_hazy_scenes": True, "min_scenes_kept": 9})
    assert all(keep) and "skipped" in dec[-1]["reason"]                                # refuses to leave too few scenes
    assert settings({"hazy_ndvi_drop": 0.2})["hazy_ndvi_drop"] == 0.2 and settings(None)["dedupe_scenes"] is True


def _write(root, window, name, scene_id, red, nir, size=100):
    r = np.full((size, size), red, "float32"); n = np.full((size, size), nir, "float32")
    meta = {"scene_id": scene_id, "date": name[:10], "crs": "EPSG:32643", "transform": TF, "width": size, "height": size, "valid_fraction": 1.0}
    save_stack(Path(root) / "data" / "stacks" / window / f"{name}.npz", {"red": r, "nir": n, "swir22": r, "valid": np.ones((size, size), bool)}, meta)


def test_load_window_drops_duplicates_and_optionally_hazy_scenes_and_reports_it():
    with tempfile.TemporaryDirectory() as tmp:
        for k in range(8):                                   # eight normal dates, NDVI 0.5 (red 0.08, nir 0.24)
            _write(tmp, "after", f"2024-10-{10 + k:02d}_a", f"S2B_43RGM_202410{10 + k}_0_L2A", 0.08, 0.24)
        _write(tmp, "after", "2024-10-18_dup", "S2B_43RGM_20241017_1_L2A", 0.08, 0.24)       # newer version of the 17th
        _write(tmp, "after", "2024-11-04_haze", "S2B_43RGM_20241104_0_L2A", 0.20, 0.30)     # smog: red up, NDVI 0.2
        _write(tmp, "after", "2024-11-14_haze", "S2B_43RGM_20241114_0_L2A", 0.22, 0.30)
        base = load_window(tmp, "after", min_obs=2, quality={"dedupe_scenes": False})
        assert base["n_dates"] == 11 and base["scenes_dropped"] == []
        d = load_window(tmp, "after", min_obs=2)                                              # defaults
        assert d["n_dates"] == 10 and [x["scene_id"] for x in d["scenes_dropped"]] == ["S2B_43RGM_20241017_0_L2A"]
        assert "duplicate" in d["scenes_dropped"][0]["reason"]
        h = load_window(tmp, "after", min_obs=2, quality={"drop_hazy_scenes": True})
        assert h["n_dates"] == 8 and len(h["scenes_dropped"]) == 3 and abs(float(np.nanmedian(h["ndvi"])) - 0.5) < 1e-6
        assert sum("hazy" in x["reason"] for x in h["scenes_dropped"]) == 2
        skipped = load_window(tmp, "after", min_obs=2, quality={"drop_hazy_scenes": True, "min_scenes_kept": 9})
        assert skipped["n_dates"] == 10 and skipped["scene_notes"] and "skipped" in skipped["scene_notes"][0]
        assert all({"file", "scene_id", "valid_share", "red_median", "ndvi_median"} <= set(u) for u in h["scenes_used"])
