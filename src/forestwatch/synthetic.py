"""Synthetic scenes so the whole pipeline can be developed and tested offline.

NOT real data. Numbers produced from it demonstrate that the code works,
never that the method works on real satellite imagery.
"""
from __future__ import annotations
import numpy as np
from scipy import ndimage


def _smooth_noise(rng, h, w, sigma):
    f = ndimage.gaussian_filter(rng.standard_normal((h, w)), sigma)
    return (f - f.mean()) / f.std()


def make_scene_pair(h=512, w=512, seed=0, n_clear=25, season_dip=0.0,
                    noise=0.03, cloud_blobs=4):
    """Return a dict with before/after NDVI, validity masks and ground truth.

    season_dip: extra NDVI loss on all vegetation in the 'after' image, imitating
    dry-season leaf drop (a false-alarm source for cross-season comparison).
    """
    rng = np.random.default_rng(seed)
    field = _smooth_noise(rng, h, w, 18)
    forest = field > -0.2                                   # about 58% vegetated
    base = np.where(forest, 0.65 + 0.08 * _smooth_noise(rng, h, w, 6), 0.18)

    truth = np.zeros((h, w), dtype=bool)
    yy, xx = np.mgrid[0:h, 0:w]
    for _ in range(n_clear):
        cy, cx = rng.integers(20, h - 20), rng.integers(20, w - 20)
        ry, rx = rng.integers(4, 12), rng.integers(4, 12)
        blob = ((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2 <= 1.0
        truth |= blob & forest

    before = base + noise * rng.standard_normal((h, w))
    after = np.where(truth, 0.2, base)
    after = after - season_dip * (forest & ~truth) * (0.6 + 0.4 * rng.random((h, w)))
    after = after + noise * rng.standard_normal((h, w))

    valid_b = np.ones((h, w), dtype=bool)
    valid_a = np.ones((h, w), dtype=bool)
    for valid in (valid_b, valid_a):
        for _ in range(cloud_blobs):
            cy, cx, r = rng.integers(0, h), rng.integers(0, w), rng.integers(15, 40)
            valid &= ~(((yy - cy) ** 2 + (xx - cx) ** 2) <= r * r)
    truth_eval = truth & valid_b & valid_a                 # cannot score hidden pixels
    return {"ndvi_before": before.astype("float32"), "ndvi_after": after.astype("float32"),
            "valid_before": valid_b, "valid_after": valid_a,
            "truth": truth_eval, "forest": forest}
