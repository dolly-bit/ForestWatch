# Phase 1 - baseline audit: how to run it

Run from the project folder with your virtual environment active.

    # 0. protect your labels FIRST (never edit the original)
    New-Item -ItemType Directory -Force data\labels
    Copy-Item outputs\review\review.csv data\labels\review_v1_original.csv
    Get-FileHash data\labels\review_v1_original.csv

    # 1. tests
    python -m pytest -q

    # 2. can the reviewed sample be regenerated?  (needs the SAME config and stacks, no 'exclusions' section; a few minutes)
    python scripts/verify_baseline.py

    # 3. provenance record + artifact inventory (use any ID you like; it is assigned now, not when the run happened)
    python scripts/record_run.py --run-id baseline-audit-1
    python scripts/inventory_artifacts.py --run-id baseline-audit-1

    # 4. candidate-level statistics + audit-trail template
    python scripts/summarize_review.py --init-annotations data/labels/review_annotations.csv

    # 5. plan the next evaluation: spatial split, frozen with a checksum
    python scripts/make_split_manifest.py

Then edit by hand (they contain facts only you can confirm): `sampling_protocol.md`, `labeling_protocol.md`,
`known_limitations.md`. Search each file for CONFIRM.
