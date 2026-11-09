"""Scene selection before compositing: remove duplicate processing versions and (optionally) hazy scenes.

Why: the catalog can list the same acquisition twice (reprocessed versions, ids ending _0_L2A and _1_L2A), which
double-weights that date in a median; and post-Diwali smog brightens the red band and lowers NDVI on some dates,
which biases a window's composite and creates false 'drops' between windows.
The haze test is a HEURISTIC relative to the other scenes of the same window, meant to point at suspect dates."""
from __future__ import annotations
import re
import numpy as np

_ID = re.compile(r"^(?P<base>.+)_(?P<ver>\d+)_L2A$")
DEFAULTS = {"dedupe_scenes": True, "drop_hazy_scenes": False, "hazy_ndvi_drop": 0.10, "hazy_red_rise": 0.03,
            "min_scenes_kept": 6, "min_valid_for_reference": 0.5, "min_valid_pixels": 5000}


def settings(quality: dict | None) -> dict:
    return {**DEFAULTS, **(quality or {})}


def parse_scene_id(scene_id: str):
    """'S2B_43RGM_20241030_1_L2A' -> ('S2B_43RGM_20241030', 1); ids that do not match return (id, None)."""
    m = _ID.match(scene_id or "")
    return (m.group("base"), int(m.group("ver"))) if m else (scene_id, None)


def dedupe_flags(scene_ids) -> list[bool]:
    """True = keep. Among scenes that differ only by the processing-version number, keep the highest."""
    best: dict = {}
    for i, sid in enumerate(scene_ids):
        base, ver = parse_scene_id(sid)
        if ver is not None and (base not in best or ver > best[base][0]):
            best[base] = (ver, i)
    return [parse_scene_id(sid)[1] is None or best[parse_scene_id(sid)[0]][1] == i for i, sid in enumerate(scene_ids)]


def scene_stats(arr: dict, ndvi_array: np.ndarray) -> dict:
    v = arr["valid"] & (arr["red"] + arr["nir"] > 0)
    n = int(v.sum())
    return {"valid_share": float(arr["valid"].mean()), "n_valid": n,
            "red_median": float(np.median(arr["red"][v])) if n else float("nan"),
            "ndvi_median": float(np.median(ndvi_array[v])) if n else float("nan")}


def hazy_flags(stats, ndvi_drop: float, red_rise: float, min_valid_ref: float, min_valid_pixels: int):
    """Per scene: True (hazy), False, or None (cannot judge). Reference = scenes with enough clear imagery."""
    ref = [s for s in stats if s["valid_share"] >= min_valid_ref and s["n_valid"] >= min_valid_pixels]
    if len(ref) < 3:
        return [None] * len(stats)
    ref_n = float(np.median([s["ndvi_median"] for s in ref]))
    ref_r = float(np.median([s["red_median"] for s in ref]))
    out = []
    for s in stats:
        if s["n_valid"] < min_valid_pixels or not np.isfinite(s["ndvi_median"]):
            out.append(None)
        else:
            out.append(bool(s["ndvi_median"] < ref_n - ndvi_drop or s["red_median"] > ref_r + red_rise))
    return out


def select_scenes(ids, stats, quality: dict | None):
    """Decide which scenes enter the composite. Returns (keep: list[bool], decisions: list[dict])."""
    q = settings(quality)
    n = len(ids)
    keep = [True] * n
    reasons = [""] * n
    if q["dedupe_scenes"]:
        for i, k in enumerate(dedupe_flags(ids)):
            if not k:
                keep[i], reasons[i] = False, "duplicate processing version (a newer one is kept)"
    note = ""
    if q["drop_hazy_scenes"]:
        idx = [i for i in range(n) if keep[i]]
        flags = hazy_flags([stats[i] for i in idx], q["hazy_ndvi_drop"], q["hazy_red_rise"],
                           q["min_valid_for_reference"], q["min_valid_pixels"])
        hazy = [i for i, f in zip(idx, flags) if f]
        if len(idx) - len(hazy) >= q["min_scenes_kept"]:
            for i in hazy:
                keep[i], reasons[i] = False, "looks hazy compared with the rest of its window (low NDVI / high red)"
        elif hazy:
            note = f"hazy-scene dropping skipped: it would leave {len(idx) - len(hazy)} scenes (< min_scenes_kept {q['min_scenes_kept']})"
    decisions = [{"index": i, "kept": keep[i], "reason": reasons[i]} for i in range(n)]
    if note:
        decisions.append({"index": None, "kept": None, "reason": note})
    return keep, decisions
