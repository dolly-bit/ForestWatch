"""Shared loading for the Phase 2 scripts."""
from __future__ import annotations
import json
from pathlib import Path

from ..config import load_config
from ..audit import sha256_file
from .schema import load_reference_config, read_rows


def stack_meta(root) -> dict:
    files = sorted((Path(root) / "data" / "stacks" / "after").glob("*.json"))
    if not files:
        raise FileNotFoundError("No stacks in data/stacks/after: build them first (build_stacks.py)")
    return json.loads(files[0].read_text())


def load_context(root):
    root = Path(root)
    cfg = load_config(root / "configs" / "aravalli.yaml")
    ref = load_reference_config(root / "configs" / "reference.yaml")
    meta = stack_meta(root)
    return cfg, ref, meta, (meta["height"], meta["width"])


def load_frozen_manifest(root):
    """The Phase 1 manifest, refusing to continue if it no longer matches its frozen checksum."""
    root = Path(root)
    path = root / "data" / "labels" / "split_manifest.csv"
    sha = path.with_suffix(".sha256")
    if not path.exists() or not sha.exists():
        raise FileNotFoundError("Frozen split manifest missing: run scripts/make_split_manifest.py first")
    import hashlib
    ok = hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest() == sha.read_text().strip()
    if not ok:
        raise RuntimeError("split_manifest.csv no longer matches its frozen checksum. Do not continue: the test split must not move.")
    return read_rows(path), sha256_file(path)
