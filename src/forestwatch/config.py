"""Load the YAML configuration into plain dictionaries with light validation."""
from __future__ import annotations
from pathlib import Path
import yaml

REQUIRED = ["region", "stac", "windows", "cloud_mask", "baseline", "split"]


def load_config(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    missing = [k for k in REQUIRED if k not in cfg]
    if missing:
        raise ValueError(f"Config is missing sections: {missing}")
    lon0, lat0, lon1, lat1 = cfg["region"]["bbox"]
    if not (lon0 < lon1 and lat0 < lat1):
        raise ValueError("bbox must be [lon_min, lat_min, lon_max, lat_max]")
    if abs(sum(cfg["split"]["fractions"]) - 1.0) > 1e-6:
        raise ValueError("split fractions must sum to 1")
    return cfg
