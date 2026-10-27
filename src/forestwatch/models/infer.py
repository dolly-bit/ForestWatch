"""Sliding-window inference over a full raster (numpy core is testable without torch)."""
from __future__ import annotations
import numpy as np


def window_starts(n: int, patch: int, stride: int) -> list[int]:
    if n < patch:
        raise ValueError(f"Image side {n} is smaller than patch size {patch}")
    starts = list(range(0, n - patch + 1, stride))
    if starts[-1] != n - patch:
        starts.append(n - patch)                    # make sure the far edge is covered
    return starts


def predict_full(predict_fn, X: np.ndarray, patch: int, stride: int, batch_size: int = 8) -> np.ndarray:
    """X: (C, H, W). predict_fn: (B, C, p, p) float32 -> (B, p, p) probabilities.
    Overlapping windows are averaged."""
    _, H, W = X.shape
    acc = np.zeros((H, W), dtype="float32")
    cnt = np.zeros((H, W), dtype="float32")
    origins = [(r, c) for r in window_starts(H, patch, stride) for c in window_starts(W, patch, stride)]
    for i in range(0, len(origins), batch_size):
        chunk = origins[i:i + batch_size]
        batch = np.stack([X[:, r:r + patch, c:c + patch] for r, c in chunk]).astype("float32")
        probs = predict_fn(batch)
        for (r, c), p in zip(chunk, probs):
            acc[r:r + patch, c:c + patch] += p
            cnt[r:r + patch, c:c + patch] += 1
    return acc / np.maximum(cnt, 1)


def load_checkpoint(path, device=None):
    """Return (predict_fn, checkpoint_dict). Needs torch."""
    import torch
    from .unet import UNet
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(path, map_location=device)
    model = UNet(ck["in_channels"], ck["base_channels"]).to(device)
    model.load_state_dict(ck["state_dict"]); model.eval()

    def predict_fn(batch: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            t = torch.from_numpy(batch).to(device)
            return torch.sigmoid(model(t)).cpu().numpy()
    return predict_fn, ck
