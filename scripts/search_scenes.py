"""Step 1 (needs network): list candidate Sentinel-2 scenes for both windows."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.config import load_config
from forestwatch.data.stac_search import search_scenes, save_catalog

ROOT = Path(__file__).resolve().parents[1]
cfg = load_config(ROOT / "configs" / "aravalli.yaml")
for name, (start, end) in cfg["windows"].items():
    scenes = search_scenes(cfg["region"]["bbox"], start, end, cfg["stac"]["url"],
                           cfg["stac"]["collection"], cfg["stac"]["max_cloud_cover"])
    save_catalog(scenes, ROOT / "data" / "raw" / f"catalog_{name}.json")
    print(f"{name}: {len(scenes)} scenes")
    for s in scenes:
        print("  ", s["datetime"][:10], s["id"], "cloud", s["cloud_cover"])
