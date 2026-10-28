# Known limitations (Phase 1)

Update the CONFIRM items after running scripts/verify_baseline.py and summarize_review.py.

## Reproducibility
- Baseline reproducible? CONFIRM from reproduction_check.json: PASS = the reviewed candidates, their areas, the
  random sample and the seasonal flags were regenerated exactly; FAIL = treat the old run as not reproduced.
- The original run command and timestamp were not logged; the run ID is assigned retrospectively.
- Scene IDs come from the stacks on disk; the STAC search results themselves were not saved.

## Sample and labels
- Sampling frame: candidates >= min area (see sampling_protocol.md); results do not extend to smaller ones.
- Sample size is small (decided cases are in review_summary.md); intervals are wide, subgroup results are anecdotal.
- Labels come from one reviewer, with unknown imagery dates, who saw NDVI numbers and filter status (not blind).
- The meaning of 'y' is not settled (see labeling_protocol.md, OPEN DECISION).

## Post-hoc analyses that reused the same reviewed labels (so results are optimistic or exploratory)
- Farmland false-alarm cluster: 9 of 9 reviewed detections inside one small area were judged not real. Found AFTER
  looking at the labels. Reported as error analysis only.
- Cropland mask (ESA WorldCover class 40): tested by re-scoring the same sample. It removed 43 of 58 judged
  detections, 34 of them judged real, and did not improve precision. Rejected; not applied to the baseline.
- Sentinel-1 radar cross-check: only 26 of 58 rows had usable radar (21 y, 5 n); VH AUC 0.67 (95% CI 0.38 to 0.91),
  VV AUC 0.51. Inconclusive.
- CONFIRM whether any manual exclusion box was ever applied to a delivered result (if yes, list it here).

## Not available yet
- Recall: no reference labels for areas the baseline did not flag.
- Pixel-level precision, recall, F1, IoU and false alarms per 100 km2: no aligned reference masks.
- Generalisation: one study area and one before/after pair; no held-out geography has been evaluated.
- The U-Net has not been trained; the API, database and web map exist but are not part of the evaluated system.

## What may be claimed after Phase 1
- "About X% of decided candidates in a random sample (n = Y, frame = Z) were judged real by one non-blind reviewer
  using satellite photos of unknown date (95% interval A to B)."
## What may not be claimed
- Validated precision or recall, any deforestation or forest-loss accuracy, U-Net results, improvements from the
  seasonal filter, the cropland mask or radar.
