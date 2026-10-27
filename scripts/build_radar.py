"""STEP 2 - download the best single track for both windows onto your grid -> data/radar/radar.npz

Needs a free Planetary Computer account / subscription key (the data download is signed):
  pip install planetary-computer pystac-client rasterio
  then follow Microsoft's instructions to configure your key (e.g. `planetarycomputer configure`).
Takes a while: each scene is read at 10 m over your area.
"""
import json, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from forestwatch.config import load_config
from forestwatch.radar import choose_track, clean_linear, mosaic, composite_db
from forestwatch.data.download import read_band

PC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
ROOT = Path(__file__).resolve().parents[1]
cfg = load_config(ROOT / "configs" / "aravalli.yaml")
import planetary_computer
from pystac_client import Client
from rasterio.transform import Affine

meta = json.loads(sorted((ROOT / "data" / "stacks" / "after").glob("*.json"))[0].read_text())
tf, W, H, crs = Affine(*meta["transform"]), meta["width"], meta["height"], meta["crs"]
catalog = Client.open(PC_URL, modifier=planetary_computer.sign_inplace)

found = {}
for name, (start, end) in cfg["windows"].items():
    found[name] = list(catalog.search(collections=["sentinel-1-rtc"], bbox=cfg["region"]["bbox"],
                                      datetime=f"{start}/{end}").items())
track = lambda i: (i.properties.get("sat:relative_orbit"), i.properties.get("sat:orbit_state"))
best, n = choose_track(*[dict(Counter(track(i) for i in found[k])) for k in ("before", "after")])
if best is None:
    raise SystemExit("No common track in both windows. Run search_radar.py and widen the windows.")
print(f"Using track {best} ({n}+ scenes per window)")

out, info = {}, {"track": list(best)}
for name in ("before", "after"):
    by_date = defaultdict(list)
    for it in found[name]:
        if track(it) == best:
            by_date[it.datetime.date().isoformat()].append(it)
    info[f"{name}_dates"] = sorted(by_date)
    for pol in ("vh", "vv"):
        per_date = []
        for d, its in sorted(by_date.items()):
            per_date.append(mosaic([clean_linear(read_band(i.assets[pol].href, crs, tf, W, H)) for i in its]))
            print(f"  {name} {pol} {d}: {np.isfinite(per_date[-1]).mean():.0%} valid")
        out[f"{pol}_{name}_db"] = composite_db(np.stack(per_date))
(ROOT / "data" / "radar").mkdir(parents=True, exist_ok=True)
np.savez_compressed(ROOT / "data" / "radar" / "radar.npz", **out)
(ROOT / "data" / "radar" / "radar.json").write_text(json.dumps(info, indent=2))
print("Saved data/radar/radar.npz")
