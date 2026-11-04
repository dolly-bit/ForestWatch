"""Paint chip labels onto the EXACT prediction grid. Chip labels are unit-level truth: every pixel of a chip
carries its chip's class, so Phase 3 must evaluate per chip (aggregate predictions inside each chip)."""
from __future__ import annotations
import numpy as np

from ..eval.grids import check_same_grid, GridMismatchError  # noqa: F401  (re-exported)

NO_LOSS, LOSS, EXCLUDED = 0, 1, 255


def rasterize_chip_labels(rows, shape, chip_px: int, imagery_valid=None):
    """Returns (label_mask uint8: 0 / 1 / 255, valid_mask uint8: 1 = evaluate this pixel, unit_index int32 (0 = none)).
    Uncertain, ignore and unreviewed areas are 255 with valid 0; they are never turned into no_loss."""
    H, W = shape
    if imagery_valid is not None and imagery_valid.shape != (H, W):
        raise GridMismatchError(f"imagery validity has shape {imagery_valid.shape} but the grid is {(H, W)}")
    label = np.full((H, W), EXCLUDED, np.uint8)
    valid = np.zeros((H, W), np.uint8)
    index = np.zeros((H, W), np.int32)
    n_cols = W // chip_px
    for r in rows:
        r0, r1, c0, c1 = (int(r[k]) for k in ("chip_row0", "chip_row1", "chip_col0", "chip_col1"))
        if r1 > H or c1 > W or r0 < 0 or c0 < 0:
            raise ValueError(f"chip {r.get('unit_id')} lies outside the grid")
        if index[r0:r1, c0:c1].any():
            raise ValueError(f"chip {r.get('unit_id')} overlaps another labelled chip")
        index[r0:r1, c0:c1] = (r0 // chip_px) * n_cols + (c0 // chip_px) + 1
        cls = r["class_label"]
        if cls in ("loss", "no_loss"):
            label[r0:r1, c0:c1] = LOSS if cls == "loss" else NO_LOSS
            ok = np.ones((r1 - r0, c1 - c0), bool) if imagery_valid is None else imagery_valid[r0:r1, c0:c1]
            valid[r0:r1, c0:c1] = ok.astype(np.uint8)
    return label, valid, index


def write_geotiff(path, array, meta: dict, dtype: str, nodata=None) -> None:
    import rasterio
    from rasterio.transform import Affine
    with rasterio.open(path, "w", driver="GTiff", height=array.shape[0], width=array.shape[1], count=1, dtype=dtype,
                       crs=meta["crs"], transform=Affine(*meta["transform"][:6]), nodata=nodata,
                       compress="deflate") as dst:
        dst.write(array.astype(dtype), 1)


def read_grid_meta(path) -> dict:
    import rasterio
    with rasterio.open(path) as src:
        t = src.transform
        return {"crs": str(src.crs), "width": src.width, "height": src.height, "transform": [t.a, t.b, t.c, t.d, t.e, t.f]}
