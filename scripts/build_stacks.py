"""Step 2 (needs network + rasterio): download scenes onto the common grid."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.config import load_config
from forestwatch.data.download import build_scene_stack

ROOT = Path(__file__).resolve().parents[1]
cfg = load_config(ROOT / "configs" / "aravalli.yaml")
for name in cfg["windows"]:
    catalog = json.loads((ROOT / "data" / "raw" / f"catalog_{name}.json").read_text())
    for scene in catalog:
        path, meta = build_scene_stack(scene, cfg, ROOT / "data" / "stacks" / name)
        print(f"{name}: {meta['date']} valid={meta['valid_fraction']:.0%} -> {path}")
