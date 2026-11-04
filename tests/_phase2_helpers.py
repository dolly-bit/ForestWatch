import sys
import types
import numpy as np

from forestwatch.manifest import build_manifest
from forestwatch.reference.frame import build_frame
from forestwatch.reference.schema import load_reference_config
from pathlib import Path
from test_phase2 import TRANSFORM

ROOT = Path(__file__).resolve().parents[1]
CRS = "EPSG:32643"
SPLIT_CFG = {"block_size_px": 64, "fractions": [0.6, 0.2, 0.2], "seed": 42, "buffer_blocks": 1, "group_blocks": 2}
SHAPE = (256, 256)
META = {"crs": CRS, "width": 256, "height": 256, "transform": list(TRANSFORM)}


def ref_cfg():
    return load_reference_config(ROOT / "configs" / "reference.yaml")


def stub_pyproj():
    class T:
        @staticmethod
        def from_crs(src, dst, always_xy=True):
            class X:
                def transform(self, a, b):
                    a, b = np.asarray(a, float), np.asarray(b, float)
                    if src == "EPSG:4326":
                        return 500000 + (a - 77.0) * 1e5, 2999000 + (b - 28.0) * 1e5
                    return 77.0 + (a - 500000) / 1e5, 28.0 + (b - 2999000) / 1e5
            return X()
    m = types.ModuleType("pyproj")
    m.Transformer = T
    return m


class WithPyproj:
    def __enter__(self):
        self.saved = sys.modules.get("pyproj")
        sys.modules["pyproj"] = stub_pyproj()

    def __exit__(self, *a):
        if self.saved is None:
            sys.modules.pop("pyproj", None)
        else:
            sys.modules["pyproj"] = self.saved


def make_frame(seed=0):
    rng = np.random.default_rng(seed)
    manifest = build_manifest(SPLIT_CFG, META, "t")
    mask = np.zeros(SHAPE, bool)
    drop = np.full(SHAPE, 0.05, "float32")
    for _ in range(40):                                  # some detections and some near-misses
        r, c = rng.integers(0, 230, 2)
        mask[r:r + 12, c:c + 12] = True
        drop[r:r + 12, c:c + 12] = 0.5
    for _ in range(30):
        r, c = rng.integers(0, 230, 2)
        drop[r:r + 6, c:c + 6] = np.maximum(drop[r:r + 6, c:c + 6], 0.2)
    valid = np.ones(SHAPE, bool)
    valid[:32, :32] = False                              # one fully unobserved chip
    lc = rng.choice([10, 20, 40, 50], size=SHAPE).astype("uint8")
    rows = build_frame(SHAPE, 32, 64, manifest, mask, drop, valid, lc, ref_cfg(), ref_cfg()["landcover_groups"])
    return rows, manifest
