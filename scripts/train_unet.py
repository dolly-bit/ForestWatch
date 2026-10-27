"""Train the U-Net on your labels (needs torch, stacks and data/labels/change.npy)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from forestwatch.config import load_config
from forestwatch.pipeline import load_window, feature_stack, split_maps
from forestwatch.models.train import train_model

ROOT = Path(__file__).resolve().parents[1]
cfg = load_config(ROOT / "configs" / "aravalli.yaml")
min_obs = cfg["cloud_mask"]["min_valid_observations"]
before, after = load_window(ROOT, "before", min_obs), load_window(ROOT, "after", min_obs)
X, valid = feature_stack(before, after)
label_path = ROOT / "data" / "labels" / "change.npy"
if not label_path.exists():
    raise SystemExit("Missing data/labels/change.npy. Run scripts/make_labels.py first.")
y = np.load(label_path).astype(bool) & valid
split, _ = split_maps(cfg, y.shape)
print(f"Features {X.shape}, positives {int(y.sum())} px, device auto-selected")
history = train_model(X, y, split, cfg["model"], ROOT / cfg["model"]["checkpoint"])
best = max((h for h in history if h["val_f1"] is not None), key=lambda h: h["val_f1"])
print("Best validation F1:", best)
