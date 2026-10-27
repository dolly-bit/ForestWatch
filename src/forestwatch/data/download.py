"""Read one scene onto a COMMON grid and save it as a stack. Needs rasterio.

Scenes from different orbits/tiles have different pixel grids, so every band is
reprojected onto one fixed target grid (UTM, 10 m) with a WarpedVRT. That makes
all dates pixel-aligned, which change detection requires.

UNTESTED in the development sandbox (no network, no rasterio): run it on one
scene first and inspect the output in QGIS.
"""
from __future__ import annotations
from datetime import datetime
import numpy as np
from ..preprocess.cloudmask import valid_mask_from_scl
from ..preprocess.indices import scale_reflectance
from .stack_io import save_stack


def make_target_grid(bbox, crs, resolution_m=10):
    from rasterio.warp import transform_bounds
    from rasterio.transform import from_origin
    x0, y0, x1, y1 = transform_bounds("EPSG:4326", crs, *bbox)
    x0, y1 = np.floor(x0 / resolution_m) * resolution_m, np.ceil(y1 / resolution_m) * resolution_m
    width = int(np.ceil((x1 - x0) / resolution_m))
    height = int(np.ceil((y1 - y0) / resolution_m))
    return from_origin(x0, y1, resolution_m, resolution_m), width, height


def read_band(href, crs, transform, width, height, categorical=False):
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.vrt import WarpedVRT
    res = Resampling.nearest if categorical else Resampling.bilinear
    with rasterio.open(href) as src:
        with WarpedVRT(src, crs=crs, transform=transform, width=width, height=height, resampling=res) as vrt:
            return vrt.read(1)


def build_scene_stack(scene, cfg, out_dir):
    crs = cfg["region"]["crs"]
    transform, w, h = make_target_grid(cfg["region"]["bbox"], crs, cfg["region"]["resolution_m"])
    acq = datetime.fromisoformat(scene["datetime"].replace("Z", "+00:00")).date()
    a = scene["assets"]
    red = scale_reflectance(read_band(a["red"], crs, transform, w, h), acq)
    nir = scale_reflectance(read_band(a["nir"], crs, transform, w, h), acq)
    swir = scale_reflectance(read_band(a["swir22"], crs, transform, w, h), acq)
    scl = read_band(a["scl"], crs, transform, w, h, categorical=True)
    valid = valid_mask_from_scl(scl, cfg["cloud_mask"]["valid_scl_classes"])
    meta = {"scene_id": scene["id"], "date": acq.isoformat(), "crs": crs,
            "transform": list(transform)[:6], "width": w, "height": h,
            "valid_fraction": float(valid.mean())}
    path = f"{out_dir}/{acq.isoformat()}_{scene['id']}.npz"
    save_stack(path, {"red": red, "nir": nir, "swir22": swir, "valid": valid}, meta)
    return path, meta
