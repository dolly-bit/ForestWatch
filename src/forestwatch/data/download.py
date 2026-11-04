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
from ..preprocess.indices import scale_reflectance, scale_with_catalog
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


def _reflectance(dn, band, scene, cfg, acq):
    """How to turn digital numbers into reflectance. cfg['reflectance']['mode']:
      'auto'      (default) 1) the catalog's own scale/offset if recorded, 2) config boa_add_offset, 3) the date rule
      'none'      DN / 10000 with NO offset (use when the data turns out not to carry the +1000 offset)
      'date_rule' subtract 1000 DN for scenes from 2022-01-25 on (the original behaviour)"""
    r = cfg.get("reflectance") or {}
    mode = r.get("mode", "auto")
    if mode == "none":
        return scale_reflectance(dn, acq, offset_dn=0.0), "mode none: DN/10000, no offset"
    if mode == "date_rule":
        return scale_reflectance(dn, acq), "mode date_rule: offset -1000 from 2022-01-25"
    if mode != "auto":
        raise ValueError(f"unknown reflectance mode {mode!r}")
    info = (scene.get("raster") or {}).get(band) or {}
    if "scale" in info and "offset" in info:
        return scale_with_catalog(dn, info["scale"], info["offset"]), f"catalog scale={info['scale']} offset={info['offset']}"
    if r.get("boa_add_offset") is not None:
        return scale_reflectance(dn, acq, offset_dn=float(r["boa_add_offset"])), f"config boa_add_offset={r['boa_add_offset']}"
    return scale_reflectance(dn, acq), "date rule (offset -1000 from 2022-01-25); catalog declared nothing"


RED_ZERO_REJECT = 0.20      # more exact-zero red values than this among clear pixels: the scaling is implausible
RED_ZERO_OK = 0.05          # ... and a replacement is accepted only if it brings the share below this


def build_scene_stack(scene, cfg, out_dir):
    crs = cfg["region"]["crs"]
    transform, w, h = make_target_grid(cfg["region"]["bbox"], crs, cfg["region"]["resolution_m"])
    acq = datetime.fromisoformat(scene["datetime"].replace("Z", "+00:00")).date()
    a = scene["assets"]
    dn = {b: read_band(a[b], crs, transform, w, h) for b in ("red", "nir", "swir22")}
    scl = read_band(a["scl"], crs, transform, w, h, categorical=True)
    valid = valid_mask_from_scl(scl, cfg["cloud_mask"]["valid_scl_classes"])
    bands, how = {}, None
    for b in dn:
        bands[b], h_b = _reflectance(dn[b], b, scene, cfg, acq)
        how = how or h_b
    zero = float((bands["red"][valid] == 0).mean()) if valid.any() else None
    mode = (cfg.get("reflectance") or {}).get("mode", "auto")
    if mode == "auto" and zero is not None and zero > RED_ZERO_REJECT:
        # The declared offset contradicts the pixel values (a catalog can say -0.1 while the data carries none).
        alt = {b: scale_reflectance(dn[b], acq, offset_dn=0.0) for b in dn}
        alt_zero = float((alt["red"][valid] == 0).mean())
        if alt_zero < RED_ZERO_OK:
            how = (f"auto: '{how}' REJECTED (red==0 on {zero:.0%} of clear pixels); "
                   f"used DN/10000 with no offset (red==0 now {alt_zero:.1%})")
            bands, zero = alt, alt_zero
    meta = {"scene_id": scene["id"], "date": acq.isoformat(), "crs": crs,
            "transform": list(transform)[:6], "width": w, "height": h,
            "valid_fraction": float(valid.mean()), "reflectance_scaling": how, "red_zero_fraction": zero}
    path = f"{out_dir}/{acq.isoformat()}_{scene['id']}.npz"
    save_stack(path, {"red": bands["red"], "nir": bands["nir"], "swir22": bands["swir22"], "valid": valid}, meta)
    return path, meta
