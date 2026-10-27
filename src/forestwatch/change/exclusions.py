"""Areas to ignore: cropland (from a land-cover raster) and/or manual lon/lat boxes.

Why: seasonal crop cycles look like vegetation loss to an NDVI-based detector.
Config (all optional):
  exclusions:
    landcover_file: data/landcover/landcover_grid.npy   # made by scripts/prepare_landcover.py
    exclude_classes: [40]                               # ESA WorldCover: 40 = cropland
    exclude_boxes: [[lon_min, lat_min, lon_max, lat_max]]   # manual stopgap; disclose it in your report
Lon/lat conversions need pyproj.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np


def lonlat_to_rowcol(lon, lat, transform, crs):
    from pyproj import Transformer
    x, y = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(lon, lat)
    a, b, c, d, e, f = transform
    return int(np.floor((y - f) / e)), int(np.floor((x - c) / a))


def box_to_slices(box, transform, crs, shape):
    from pyproj import Transformer
    lon0, lat0, lon1, lat1 = box
    tr = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    pts = [tr.transform(lon, lat) for lon, lat in ((lon0, lat0), (lon0, lat1), (lon1, lat0), (lon1, lat1))]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    a, b, c, d, e, f = transform
    h, w = shape
    c0, c1 = int(np.floor((min(xs) - c) / a)), int(np.ceil((max(xs) - c) / a))
    r0, r1 = int(np.floor((max(ys) - f) / e)), int(np.ceil((min(ys) - f) / e))
    return slice(max(r0, 0), min(r1, h)), slice(max(c0, 0), min(c1, w))


def exclusion_mask(cfg: dict, root, meta: dict, shape) -> np.ndarray:
    """Boolean array, True where detections must be ignored."""
    ex = cfg.get("exclusions") or {}
    out = np.zeros(shape, dtype=bool)
    lc = ex.get("landcover_file")
    if lc:
        path = Path(root) / lc
        if not path.exists():
            raise FileNotFoundError(f"exclusions.landcover_file is set but {path} does not exist. "
                                    "Run scripts/prepare_landcover.py or set it to null.")
        arr = np.load(path)
        if arr.shape != tuple(shape):
            raise ValueError(f"Land-cover grid {arr.shape} does not match the stack grid {tuple(shape)}")
        out |= np.isin(arr, ex.get("exclude_classes", [40]))
    for box in ex.get("exclude_boxes") or []:
        rs, cs = box_to_slices(box, tuple(meta["transform"]), meta["crs"], shape)
        out[rs, cs] = True
    return out
