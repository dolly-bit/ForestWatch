"""Grid-consistency checks: fail loudly when two rasters/masks do not share a grid."""
from __future__ import annotations
import numpy as np


class GridMismatchError(ValueError):
    pass


def check_same_shape(name_a: str, a: np.ndarray, name_b: str, b: np.ndarray) -> None:
    if a.shape != b.shape:
        raise GridMismatchError(f"{name_a} has shape {a.shape} but {name_b} has shape {b.shape}")


def check_same_grid(meta_a: dict, meta_b: dict, name_a: str = "A", name_b: str = "B", tol: float = 1e-6) -> None:
    """meta dicts need crs, width, height and transform (a, b, c, d, e, f)."""
    problems = []
    if str(meta_a["crs"]) != str(meta_b["crs"]):
        problems.append(f"CRS differs: {meta_a['crs']} vs {meta_b['crs']}")
    if (meta_a["width"], meta_a["height"]) != (meta_b["width"], meta_b["height"]):
        problems.append(f"size differs: {meta_a['width']}x{meta_a['height']} vs {meta_b['width']}x{meta_b['height']}")
    ta, tb = np.asarray(meta_a["transform"][:6], float), np.asarray(meta_b["transform"][:6], float)
    if not np.allclose(ta, tb, atol=tol, rtol=0):
        problems.append(f"transform differs: {ta.tolist()} vs {tb.tolist()}")
    if problems:
        raise GridMismatchError(f"{name_a} and {name_b} are not on the same grid: " + "; ".join(problems))
