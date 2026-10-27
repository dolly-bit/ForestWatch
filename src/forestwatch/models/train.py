"""Train the bi-temporal U-Net on spatially split patches. Needs torch."""
from __future__ import annotations
import csv
import random
from pathlib import Path
import numpy as np

from ..preprocess.splits import TRAIN, VAL
from ..eval.metrics import pixel_metrics
from .dataset import valid_patch_origins, patch_positive_fraction, sampling_weights, make_torch_dataset
from .infer import predict_full


def _seed_everything(seed: int):
    import torch
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def train_model(X, y, split_map, mcfg: dict, out_path, device=None) -> list[dict]:
    """X: (C, H, W) features, y: (H, W) bool labels, split_map: (H, W) split labels.
    Saves the best checkpoint (by validation F1) and a learning-curve CSV. Returns the history."""
    import torch
    from torch.utils.data import DataLoader, WeightedRandomSampler
    from .unet import UNet, dice_bce_loss

    _seed_everything(mcfg["seed"])
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    P, S = mcfg["patch_size"], mcfg["stride"]

    origins = valid_patch_origins(split_map, TRAIN, P, S)
    if not origins:
        raise ValueError("No training patches fit inside TRAIN blocks. Use a larger area or a smaller patch_size.")
    frac = patch_positive_fraction(y, origins, P)
    if (frac > 0).sum() == 0:
        raise ValueError("No change pixels inside TRAIN blocks. Draw more labels or check the split.")
    weights = sampling_weights(frac, mcfg["positive_oversample"])
    ds = make_torch_dataset(X, y, origins, P, augment=True, seed=mcfg["seed"])
    sampler = WeightedRandomSampler(torch.tensor(weights), num_samples=len(origins), replacement=True)
    loader = DataLoader(ds, batch_size=mcfg["batch_size"], sampler=sampler, drop_last=len(origins) > mcfg["batch_size"])

    pos = float(y[split_map == TRAIN].mean())
    pos_weight = float(min(max((1 - pos) / max(pos, 1e-6), 1.0), 10.0))
    model = UNet(X.shape[0], mcfg["base_channels"]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=mcfg["lr"], weight_decay=1e-4)
    val_region = split_map == VAL

    def predict_fn(batch):
        model.eval()
        with torch.no_grad():
            return torch.sigmoid(model(torch.from_numpy(batch).to(device))).cpu().numpy()

    history, best = [], {"f1": -1.0}
    out_path = Path(out_path); out_path.parent.mkdir(parents=True, exist_ok=True)
    for epoch in range(1, mcfg["epochs"] + 1):
        model.train(); losses = []
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            loss = dice_bce_loss(model(xb), yb, pos_weight)
            loss.backward(); opt.step(); losses.append(float(loss))
        row = {"epoch": epoch, "train_loss": float(np.mean(losses)), "val_f1": None, "threshold": None}
        if epoch % mcfg["eval_every"] == 0 or epoch == mcfg["epochs"]:
            probs = predict_full(predict_fn, X, P, S)
            scores = {t: pixel_metrics(probs >= t, y, val_region)["f1"] for t in mcfg["threshold_grid"]}
            thr = max(scores, key=scores.get)
            row.update(val_f1=scores[thr], threshold=thr)
            if scores[thr] > best["f1"]:
                best = {"f1": scores[thr], "epoch": epoch}
                torch.save({"state_dict": model.state_dict(), "in_channels": X.shape[0],
                            "base_channels": mcfg["base_channels"], "threshold": float(thr),
                            "val_f1": scores[thr], "epoch": epoch, "model_cfg": mcfg}, out_path)
        history.append(row)
        print(row)
    with open(out_path.with_suffix(".csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["epoch", "train_loss", "val_f1", "threshold"])
        w.writeheader(); w.writerows(history)
    return history
