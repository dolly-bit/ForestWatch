"""Model tests (need torch). Skipped when torch is missing."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from forestwatch.models.unet import UNet, dice_bce_loss          # noqa: E402
from forestwatch.models.train import train_model                  # noqa: E402
from forestwatch.models.infer import load_checkpoint, predict_full  # noqa: E402
from forestwatch.pipeline import N_CHANNELS                       # noqa: E402
from forestwatch.preprocess.splits import assign_block_splits, pixel_split_map  # noqa: E402


def test_unet_output_shape_and_loss_decreases():
    torch.manual_seed(0)
    m = UNet(N_CHANNELS, base=8)
    x = torch.randn(4, N_CHANNELS, 64, 64)
    y = (x[:, 0] > 0).float()
    assert m(x).shape == (4, 64, 64)
    opt = torch.optim.Adam(m.parameters(), lr=1e-2)
    first = None
    for _ in range(25):
        opt.zero_grad(); loss = dice_bce_loss(m(x), y); loss.backward(); opt.step()
        first = first or float(loss)
    assert float(loss) < first


def test_training_smoke_and_checkpoint_roundtrip(tmp_path):
    rng = np.random.default_rng(0)
    H = W = 256
    X = rng.standard_normal((N_CHANNELS, H, W)).astype("float32")
    y = X[0] > 1.0                                    # learnable rule: easy synthetic target
    grid = assign_block_splits(8, 8, seed=1, buffer=1, group=2)
    split = pixel_split_map(H, W, 32, grid)
    cfg = {"patch_size": 32, "stride": 16, "base_channels": 8, "epochs": 2, "batch_size": 8, "lr": 1e-2,
           "positive_oversample": 4.0, "eval_every": 1, "threshold_grid": [0.5], "seed": 0}
    ck = tmp_path / "m.pt"
    hist = train_model(X, y, split, cfg, ck, device="cpu")
    assert ck.exists() and len(hist) == 2
    fn, meta = load_checkpoint(ck, device="cpu")
    probs = predict_full(fn, X, 32, 16)
    assert probs.shape == (H, W) and 0.0 <= probs.min() and probs.max() <= 1.0
