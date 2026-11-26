from datetime import datetime, timezone
from types import SimpleNamespace

from forestwatch.data.stac_search import _item_to_scene


def test_item_to_scene_preserves_calibration_and_provenance_properties():
    properties = {
        "eo:cloud_cover": 12.5,
        "s2:processing_baseline": "04.00",
        "earthsearch:boa_offset_applied": False,
        "platform": "sentinel-2b",
        "constellation": "sentinel-2",
        "instruments": ["msi"],
        "unrelated:property": "not copied",
    }
    assets = {
        key: SimpleNamespace(
            href=f"https://example.test/{key}.tif",
            extra_fields={"raster:bands": [{"scale": 0.0001, "offset": -0.1}]},
        )
        for key in ("red", "nir", "swir22", "scl")
    }
    item = SimpleNamespace(
        id="S2B_43RGM_20221016_0_L2A",
        datetime=datetime(2022, 10, 16, tzinfo=timezone.utc),
        properties=properties,
        assets=assets,
    )

    scene = _item_to_scene(item)

    assert scene["stac_properties"]["s2:processing_baseline"] == "04.00"
    assert scene["stac_properties"]["earthsearch:boa_offset_applied"] is False
    assert scene["stac_properties"]["platform"] == "sentinel-2b"
    assert scene["raster"]["red"] == {"scale": 0.0001, "offset": -0.1}
    assert "unrelated:property" not in scene["stac_properties"]


def test_item_to_scene_skips_items_missing_required_assets_or_datetime():
    item = SimpleNamespace(
        id="incomplete",
        datetime=None,
        properties={},
        assets={},
    )
    assert _item_to_scene(item) is None
