# Phase 2 - independent reference dataset: run order

Run from the project folder with the virtual environment active. Do NOT start at step 3 before steps 1-2 are settled.

    # 1. Is the reflectance scaling right? (your NDVI table showed a median NDVI of 1.00 for trees and shrubs)
    python scripts/check_reflectance.py
    #    if it prints SUSPECT: back up data\stacks, run search_scenes.py, build_stacks.py, check_reflectance.py again,
    #    then run the Phase 1 audit scripts again under a NEW run id (the old stacks are a different dataset)

    # 2. Import the frozen blocks into data/splits (never re-randomises)
    python scripts/create_spatial_blocks.py

    # 3. Chip sampling frame from the (corrected) baseline: detections AND non-detections
    python scripts/build_sampling_frame.py          # prints how many chips each split/stratum would need; edit configs/reference.yaml if too many

    # 4. Draw the sample and make the BLIND sheet + KML (validation first; test last)
    python scripts/select_reference_units.py --split validation --reviewer R1
    #    label data\reference\label_sheet_validation.csv  (do NOT open selected_units_*.csv)

    # 5. Merge, validate, summarise
    python scripts/ingest_labels.py --split validation
    python scripts/validate_reference_labels.py --split validation
    python scripts/summarize_reference_dataset.py --splits validation --write-manifest

    # 6. Quality check: blind re-review of 20% (wait several days)
    python scripts/rereview.py make --split validation
    python scripts/rereview.py compare --split validation

    # 7. Masks on the exact prediction grid (needs rasterio); the test split only for the final evaluation
    python scripts/rasterize_reference_labels.py --split validation --baseline-run-id <id printed in step 3>

Edit the CONFIRM items in reference_labeling_protocol.md, sampling_design.md, split_design.md and limitations.md.
