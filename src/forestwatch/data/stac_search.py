"""Find Sentinel-2 L2A scenes through a STAC API. Needs: pip install pystac-client.

NOTE: written against the Earth Search v1 layout (asset keys 'red', 'nir',
'swir22', 'scl'). Verify asset names and catalog URL before relying on it.
"""
from __future__ import annotations
import json
from pathlib import Path

ASSET_KEYS = ("red", "nir", "swir22", "scl")


def search_scenes(bbox, start, end, url, collection="sentinel-2-l2a", max_cloud=30):
    from pystac_client import Client  # lazy import: only needed with network access
    client = Client.open(url)
    search = client.search(collections=[collection], bbox=bbox, datetime=f"{start}/{end}",
                           query={"eo:cloud_cover": {"lt": max_cloud}})
    scenes = []
    for item in search.items():
        missing = [k for k in ASSET_KEYS if k not in item.assets]
        if missing:
            continue
        scenes.append({"id": item.id, "datetime": item.datetime.isoformat(),
                       "cloud_cover": item.properties.get("eo:cloud_cover"),
                       "assets": {k: item.assets[k].href for k in ASSET_KEYS}})
    scenes.sort(key=lambda s: s["datetime"])
    return scenes


def save_catalog(scenes, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(scenes, indent=2))
