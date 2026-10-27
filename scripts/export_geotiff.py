"""Export the before/after composites as GeoTIFFs so you can draw labels in QGIS.

Writes to outputs/qgis/:
  before_falsecolor.tif, after_falsecolor.tif   3-band (R=NIR, G=red, B=SWIR2). Vegetation looks red/pink,
                                                bare ground and cleared land look blue-grey/cyan.
  before_ndvi.tif, after_ndvi.tif               NDVI (-1..1)
  ndvi_drop.tif                                 before minus after (large positive = vegetation lost)
Needs rasterio (pip install -e ".[geo]").
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def stretch_to_uint8(a: np.ndarray, lo: float = 2, hi: float = 98) -> np.ndarray:
    """Percentile stretch to 1..255; 0 is reserved for 'no data'."""
    finite = np.isfinite(a)
    if not finite.any():
        return np.zeros(a.shape, np.uint8)
    l, h = np.percentile(a[finite], [lo, hi])
    if h <= l:
        h = l + 1e-6
    scaled = np.clip((a - l) / (h - l), 0, 1) * 254 + 1
    return np.where(finite, scaled, 0).astype(np.uint8)


def write_tif(path, array, meta, nodata, dtype):
    import rasterio
    from rasterio.transform import Affine
    arr = array if array.ndim == 3 else array[None]
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[1], width=arr.shape[2], count=arr.shape[0],
                       dtype=dtype, crs=meta["crs"], transform=Affine(*meta["transform"]),
                       nodata=nodata, compress="deflate") as dst:
        dst.write(arr.astype(dtype))


def main():
    from forestwatch.config import load_config
    from forestwatch.pipeline import load_window
    cfg = load_config(ROOT / "configs" / "aravalli.yaml")
    min_obs = cfg["cloud_mask"]["min_valid_observations"]
    out = ROOT / "outputs" / "qgis"
    out.mkdir(parents=True, exist_ok=True)
    wins = {n: load_window(ROOT, n, min_obs) for n in ("before", "after")}
    meta = wins["after"]["meta"]
    for name, w in wins.items():
        fc = np.stack([stretch_to_uint8(w["nir"]), stretch_to_uint8(w["red"]), stretch_to_uint8(w["swir22"])])
        write_tif(out / f"{name}_falsecolor.tif", fc, meta, 0, "uint8")
        nd = np.where(np.isfinite(w["ndvi"]), w["ndvi"], -9999)
        write_tif(out / f"{name}_ndvi.tif", nd, meta, -9999, "float32")
        print(f"{name}: {w['n_dates']} dates, {np.isfinite(w['ndvi']).mean():.0%} of pixels have a clean composite")
    drop = wins["before"]["ndvi"] - wins["after"]["ndvi"]
    write_tif(out / "ndvi_drop.tif", np.where(np.isfinite(drop), drop, -9999), meta, -9999, "float32")
    print("Saved GeoTIFFs in", out)
    print("Open them in QGIS (Layer > Add Layer > Add Raster Layer). CRS:", meta["crs"])


if __name__ == "__main__":
    main()
