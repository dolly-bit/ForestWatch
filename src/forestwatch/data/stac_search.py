"""Find Sentinel-2 L2A scenes through a STAC API.

The catalog-specific asset keys are Earth Search v1: red, nir, swir22, scl.
Keep the calibration-related item properties: asset raster metadata alone is
not sufficient to interpret Earth Search's Sentinel-2 BOA offset handling.
"""
from __future__ import annotations

import json
from pathlib import Path

ASSET_KEYS = ("red", "nir", "swir22", "scl")

# Preserve exact STAC property names so downstream code and saved catalogs
# retain provenance instead of silently discarding processing metadata.
STAC_PROPERTY_KEYS = (
    "s2:processing_baseline",
    "earthsearch:boa_offset_applied",
    "platform",
    "constellation",
    "instruments",
    "s2:product_type",
    "s2:tile_id",
    "mgrs:utm_zone",
    "mgrs:latitude_band",
    "mgrs:grid_square",
    "processing:software",
)


def search_scenes(bbox, start, end, url, collection="sentinel-2-l2a", max_cloud=30):
    from pystac_client import Client  # lazy import: only needed with network access

    client = Client.open(url)
    search = client.search(
        collections=[collection],
        bbox=bbox,
        datetime=f"{start}/{end}",
        query={"eo:cloud_cover": {"lt": max_cloud}},
    )
    scenes = []
    for item in search.items():
        scene = _item_to_scene(item)
        if scene is not None:
            scenes.append(scene)
    scenes.sort(key=lambda scene: scene["datetime"])
    return scenes


def _item_to_scene(item) -> dict | None:
    """Convert a STAC Item into the stable catalog format used by the pipeline."""
    missing = [key for key in ASSET_KEYS if key not in item.assets]
    if missing or item.datetime is None:
        return None

    properties = item.properties or {}
    stac_properties = {
        key: properties[key]
        for key in STAC_PROPERTY_KEYS
        if key in properties
    }
    return {
        "id": item.id,
        "datetime": item.datetime.isoformat(),
        "cloud_cover": properties.get("eo:cloud_cover"),
        "assets": {key: item.assets[key].href for key in ASSET_KEYS},
        "raster": {
            key: _raster_info(item.assets[key])
            for key in ASSET_KEYS
            if key != "scl"
        },
        "stac_properties": stac_properties,
    }


def _raster_info(asset) -> dict:
    """Return the scale/offset declared for the first raster band, if present."""
    bands = (asset.extra_fields or {}).get("raster:bands") or []
    band = bands[0] if bands else {}
    return {
        key: float(band[key])
        for key in ("scale", "offset")
        if key in band
    }


def save_catalog(scenes, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scenes, indent=2))
