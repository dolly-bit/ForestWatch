"""Read one scene onto a common grid and save it as a stack.

Scenes from different orbits/tiles have different pixel grids, so every band is
reprojected onto one fixed target grid (UTM, 10 m). This makes all dates
pixel-aligned, which change detection requires.
"""
from __future__ import annotations

from datetime import datetime
import warnings

import numpy as np

from ..preprocess.cloudmask import valid_mask_from_scl
from ..preprocess.indices import scale_reflectance, scale_with_catalog
from .stack_io import save_stack


def make_target_grid(bbox, crs, resolution_m=10):
    from rasterio.warp import transform_bounds
    from rasterio.transform import from_origin

    x0, y0, x1, y1 = transform_bounds("EPSG:4326", crs, *bbox)
    x0 = np.floor(x0 / resolution_m) * resolution_m
    y1 = np.ceil(y1 / resolution_m) * resolution_m
    width = int(np.ceil((x1 - x0) / resolution_m))
    height = int(np.ceil((y1 - y1) / resolution_m)) if False else int(np.ceil((y1 - y0) / resolution_m))
    return from_origin(x0, y1, resolution_m, resolution_m), width, height


def read_band(href, crs, transform, width, height, categorical=False):
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.vrt import WarpedVRT

    resampling = Resampling.nearest if categorical else Resampling.bilinear
    with rasterio.open(href) as src:
        with WarpedVRT(
            src,
            crs=crs,
            transform=transform,
            width=width,
            height=height,
            resampling=resampling,
        ) as vrt:
            return vrt.read(1)


def _reflectance(dn, band, scene, cfg, acq):
    """Convert Sentinel-2 DN using STAC metadata, without guessing on conflicts.

    Earth Search's flag means:
      True  -> the BOA offset has already been applied to the COG: do not apply it again.
      False -> the BOA offset has not been applied: use the declared raster offset.

    The legacy Earth Search collection has documented inconsistencies, so the
    pixel-level conflict check in build_scene_stack can stop suspicious scenes.
    """
    reflectance_cfg = cfg.get("reflectance") or {}
    mode = reflectance_cfg.get("mode", "auto")

    if mode == "none":
        return scale_reflectance(dn, acq, offset_dn=0.0), "mode none: DN/10000, no additional offset"
    if mode == "date_rule":
        return scale_reflectance(dn, acq), "mode date_rule: legacy -1000 DN correction"
    if mode != "auto":
        raise ValueError(f"unknown reflectance mode {mode!r}")

    raster_info = (scene.get("raster") or {}).get(band) or {}
    stac_properties = scene.get("stac_properties") or {}
    boa_offset_applied = stac_properties.get("earthsearch:boa_offset_applied")
    scale = float(raster_info.get("scale", 0.0001))

    if boa_offset_applied is True:
        return (
            scale_with_catalog(dn, scale, 0.0),
            f"Earth Search boa_offset_applied=true: scale={scale}, offset=0 (already applied)",
        )

    if boa_offset_applied is False:
        if "offset" in raster_info:
            offset = float(raster_info["offset"])
            return (
                scale_with_catalog(dn, scale, offset),
                f"Earth Search boa_offset_applied=false: catalog scale={scale}, offset={offset}",
            )
        baseline = stac_properties.get("s2:processing_baseline")
        try:
            needs_offset = float(str(baseline).split("N")[0]) >= 4.0
        except (TypeError, ValueError):
            needs_offset = acq >= datetime(2022, 1, 25).date()
        offset_dn = -1000.0 if needs_offset else 0.0
        return (
            scale_reflectance(dn, acq, offset_dn=offset_dn),
            f"Earth Search boa_offset_applied=false: raster offset missing; DN offset={offset_dn}",
        )

    if "scale" in raster_info and "offset" in raster_info:
        return (
            scale_with_catalog(dn, raster_info["scale"], raster_info["offset"]),
            f"catalog scale={raster_info['scale']} offset={raster_info['offset']} "
            "(Earth Search BOA flag unavailable)",
        )

    if reflectance_cfg.get("boa_add_offset") is not None:
        offset_dn = float(reflectance_cfg["boa_add_offset"])
        return (
            scale_reflectance(dn, acq, offset_dn=offset_dn),
            f"config boa_add_offset={offset_dn}",
        )

    return (
        scale_reflectance(dn, acq),
        "date-rule fallback: Earth Search BOA flag and catalog scale/offset unavailable",
    )


def build_scene_stack(scene, cfg, out_dir):
    crs = cfg["region"]["crs"]
    transform, width, height = make_target_grid(
        cfg["region"]["bbox"], crs, cfg["region"]["resolution_m"]
    )
    acquisition_date = datetime.fromisoformat(
        scene["datetime"].replace("Z", "+00:00")
    ).date()
    assets = scene["assets"]

    digital_numbers = {
        band: read_band(assets[band], crs, transform, width, height)
        for band in ("red", "nir", "swir22")
    }
    scl = read_band(
        assets["scl"], crs, transform, width, height, categorical=True
    )
    valid = valid_mask_from_scl(scl, cfg["cloud_mask"]["valid_scl_classes"])

    bands = {}
    scaling_decisions = {}
    for band, dn in digital_numbers.items():
        bands[band], scaling_decisions[band] = _reflectance(
            dn, band, scene, cfg, acquisition_date
        )

    red_zero_fraction = (
        float((bands["red"][valid] == 0).mean()) if valid.any() else None
    )
    reflectance_cfg = cfg.get("reflectance") or {}
    properties = scene.get("stac_properties") or {}
    red_raster = (scene.get("raster") or {}).get("red") or {}
    conflict = (
        reflectance_cfg.get("mode", "auto") == "auto"
        and properties.get("earthsearch:boa_offset_applied") is False
        and float(red_raster.get("offset", 0.0)) < 0.0
        and red_zero_fraction is not None
        and red_zero_fraction > float(reflectance_cfg.get("max_red_zero_fraction", 0.20))
    )
    if conflict:
        message = (
            f"Reflectance metadata conflict for {scene['id']}: Earth Search says "
            "boa_offset_applied=false and declares a negative red-band offset, but "
            f"{red_zero_fraction:.1%} of valid red pixels became exactly zero. "
            "The legacy collection has known metadata inconsistencies. No stack was "
            "written. Validate this scene against its source product, then explicitly "
            "choose --scaling none or configure a justified calibration."
        )
        action = reflectance_cfg.get("on_metadata_conflict", "error")
        if action == "error":
            raise ValueError(message)
        if action == "warn":
            warnings.warn(message, RuntimeWarning, stacklevel=2)
        else:
            raise ValueError(
                "reflectance.on_metadata_conflict must be 'error' or 'warn'"
            )

    meta = {
        "scene_id": scene["id"],
        "date": acquisition_date.isoformat(),
        "crs": crs,
        "transform": list(transform)[:6],
        "width": width,
        "height": height,
        "valid_fraction": float(valid.mean()),
        "reflectance_scaling": scaling_decisions,
        "red_zero_fraction": red_zero_fraction,
        "stac_properties": properties,
        "reflectance_metadata_conflict": bool(conflict),
    }
    path = f"{out_dir}/{acquisition_date.isoformat()}_{scene['id']}.npz"
    save_stack(
        path,
        {
            "red": bands["red"],
            "nir": bands["nir"],
            "swir22": bands["swir22"],
            "valid": valid,
        },
        meta,
    )
    return path, meta
