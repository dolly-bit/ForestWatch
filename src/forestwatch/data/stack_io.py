"""Save / load one acquisition date as a compressed .npz plus JSON metadata."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np


def save_stack(path, arrays: dict, meta: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)
    path.with_suffix(".json").write_text(json.dumps(meta, indent=2))


def load_stack(path):
    path = Path(path)
    with np.load(path) as z:
        arrays = {k: z[k] for k in z.files}
    meta = json.loads(path.with_suffix(".json").read_text())
    return arrays, meta
