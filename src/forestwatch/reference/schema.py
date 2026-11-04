"""Schema, configuration and CSV helpers for the Phase 2 reference dataset."""
from __future__ import annotations
import csv
from pathlib import Path
import yaml

CLASSES = ("loss", "no_loss", "uncertain", "ignore")
SPLITS = ("train", "validation", "test")
LABEL_COLUMNS = ["label_id", "unit_id", "block_id", "split", "class_label", "loss_type", "event_start", "event_end",
                 "evidence_source", "evidence_before_date", "evidence_after_date", "reviewer_id", "review_date",
                 "confidence", "review_status", "notes", "protocol_version", "dataset_version", "region", "stratum",
                 "baseline_status", "selection_probability", "chip_row0", "chip_row1", "chip_col0", "chip_col1", "crs"]
FRAME_COLUMNS = ["unit_id", "block_id", "split", "region", "chip_row0", "chip_row1", "chip_col0", "chip_col1",
                 "baseline_status", "landcover_class", "landcover_group", "stratum", "valid_fraction", "flagged_px",
                 "drop_p95", "eligible", "exclusion_reason", "selection_method", "selection_probability",
                 "geometry_path", "notes"]
SELECTED_COLUMNS = FRAME_COLUMNS + ["sampling_weight", "stratum_population", "stratum_sample"]
SHEET_COLUMNS = ["unit_id", "lat", "lon", "maps_link", "class_label", "loss_type", "confidence", "evidence_source",
                 "evidence_before_date", "evidence_after_date", "event_start", "event_end", "reviewer_id",
                 "review_date", "notes"]
MASK_ENCODING = {"no_loss": 0, "loss": 1, "excluded (uncertain / ignore / not reviewed)": 255}


def load_reference_config(path) -> dict:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))["reference"]
    missing = [k for k in ("chip_px", "seed", "allocation", "dataset_version", "protocol_version") if k not in cfg]
    if missing:
        raise ValueError(f"reference config is missing: {missing}")
    return cfg


def read_rows(path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_rows(path, rows, columns, overwrite: bool = False) -> None:
    path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} exists; refusing to overwrite (use the script's --force only if you mean it)")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def guard_test_labels(splits, allow_test: bool = False):
    """The test labels exist only for the final evaluation: asking for them must be a deliberate act."""
    if "test" in splits and not allow_test:
        raise PermissionError("Test labels are reserved for the final evaluation. Pass allow_test=True (or --final-evaluation) "
                              "only for that purpose; never for development, tuning or threshold selection.")
    return list(splits)
