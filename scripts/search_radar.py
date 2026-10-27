"""STEP 1 - feasibility check (no account needed): is there Sentinel-1 RTC data for your area and dates?

Searches the Microsoft Planetary Computer catalog and prints how many scenes exist per satellite track in
each of your two date windows. Radar is only comparable within ONE track, so you need a track with
scenes in both windows (ideally 2+ each).
"""
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.config import load_config
from forestwatch.radar import choose_track

PC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
ROOT = Path(__file__).resolve().parents[1]
cfg = load_config(ROOT / "configs" / "aravalli.yaml")

from pystac_client import Client
catalog = Client.open(PC_URL)
counts = {}
for name, (start, end) in cfg["windows"].items():
    items = list(catalog.search(collections=["sentinel-1-rtc"], bbox=cfg["region"]["bbox"],
                                datetime=f"{start}/{end}").items())
    c = Counter((i.properties.get("sat:relative_orbit"), i.properties.get("sat:orbit_state")) for i in items)
    counts[name] = dict(c)
    dates = sorted({i.datetime.date().isoformat() for i in items})
    print(f"\n{name} window {start} .. {end}: {len(items)} scenes on {len(dates)} dates")
    for k, v in sorted(c.items(), key=lambda kv: -kv[1]):
        print(f"   track (relative orbit {k[0]}, {k[1]}): {v} scenes")
best, n = choose_track(counts["before"], counts["after"])
print()
if best is None:
    print("RESULT: no track appears in BOTH windows -> radar comparison is NOT possible with this catalog.")
    print("Try widening the windows, or skip radar (mention it as future work).")
else:
    print(f"RESULT: best track = relative orbit {best[0]}, {best[1]}, with at least {n} scene(s) in each window.")
    print("Next: create a free Planetary Computer account (needed to download), then run scripts/build_radar.py")
