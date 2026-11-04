"""Import the FROZEN Phase 1 split manifest (never re-randomised) and add regions / GeoJSON."""
from __future__ import annotations
import hashlib
import json
from collections import Counter

from .schema import SPLITS


def region_for(row_block: int, col_block: int, n_rows: int, n_cols: int) -> str:
    return ("N" if row_block < n_rows / 2 else "S") + ("W" if col_block < n_cols / 2 else "E")


def prepare_blocks(manifest_rows, resolution_m: float, shape) -> list[dict]:
    """README-style manifest rows (block_id, split, region, area_km2, stratum, selection_method, notes) plus geometry fields."""
    H, W = shape
    n_r = max(int(r["row_block"]) for r in manifest_rows) + 1
    n_c = max(int(r["col_block"]) for r in manifest_rows) + 1
    out = []
    for r in manifest_rows:
        h = max(0, min(int(r["px_row1"]), H) - int(r["px_row0"]))
        w = max(0, min(int(r["px_col1"]), W) - int(r["px_col0"]))
        out.append({"block_id": int(r["block_id"]), "split": r["split"],
                    "region": region_for(int(r["row_block"]), int(r["col_block"]), n_r, n_c),
                    "area_km2": round(h * w * resolution_m ** 2 / 1e6, 4),
                    "stratum": "grouped_random_block", "selection_method": r.get("reason", ""),
                    "notes": "imported unchanged from the frozen Phase 1 manifest",
                    "row_block": int(r["row_block"]), "col_block": int(r["col_block"]),
                    "px_row0": int(r["px_row0"]), "px_row1": int(r["px_row1"]),
                    "px_col0": int(r["px_col0"]), "px_col1": int(r["px_col1"]),
                    "min_x": float(r["min_x"]), "min_y": float(r["min_y"]), "max_x": float(r["max_x"]),
                    "max_y": float(r["max_y"]), "crs": r["crs"]})
    return out


def check_blocks(blocks) -> list[str]:
    """Problems that would break spatial independence: duplicate ids, unknown splits."""
    problems = []
    ids = [b["block_id"] for b in blocks]
    dup = sorted(i for i, c in Counter(ids).items() if c > 1)
    if dup:
        problems.append(f"block ids appear more than once (so in more than one split?): {dup[:10]}")
    bad = sorted({b["split"] for b in blocks} - set(SPLITS) - {"buffer"})
    if bad:
        problems.append(f"unknown split names: {bad}")
    return problems


def hash_of_test_blocks(blocks) -> str:
    ids = ",".join(str(i) for i in sorted(b["block_id"] for b in blocks if b["split"] == "test"))
    return hashlib.sha256(ids.encode()).hexdigest()


def blocks_geojson(blocks) -> dict:
    from .export import polygon_lonlat
    feats = []
    for b in blocks:
        ring = polygon_lonlat(b["min_x"], b["min_y"], b["max_x"], b["max_y"], b["crs"])
        feats.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]},
                      "properties": {k: b[k] for k in ("block_id", "split", "region", "area_km2", "stratum")}})
    return {"type": "FeatureCollection", "features": feats}


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True)
