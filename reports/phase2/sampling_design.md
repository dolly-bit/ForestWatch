# Sampling design

## Why chips instead of polygons
Drawing accurate polygons was not feasible for a single novice reviewer. The reference unit is therefore a chip:
a 32 x 32 pixel square (320 m x 320 m, 10.24 ha) aligned to the prediction grid and nested inside one block. The label
describes the whole chip. Consequence: evaluation is UNIT-LEVEL (is there loss in the chip, and did the detector flag
the chip), not pixel-level IoU. Pixel-level metrics need polygons and can be added later for loss chips only.

## Frame and strata
- Frame: every full chip on the grid inside a train/validation/test block with at least `min_valid_fraction` clear
  imagery on both dates. Buffer-block chips and poorly observed chips are excluded (listed in sampling_frame.csv).
  Partial chips on the grid edge are not part of the frame.
- Stratum = baseline status | land-cover group:
  baseline status: `flagged` (>= min_flagged_px baseline pixels), `unflagged_near_miss` (not flagged but a strong
  NDVI drop, 95th percentile >= near_miss_drop), `unflagged_quiet`; land-cover group from the chip's majority ESA
  WorldCover class: natural (tree, shrub, grass), cropland, built_up, other.
- Non-detections are sampled on purpose: they are the only way to find what the baseline missed.

## Selection
Simple random sampling without replacement within each split x stratum, n per stratum from configs/reference.yaml
(all chips if the stratum is smaller). Inclusion probability n_h / N_h is exact and stored per unit, together with
the weight N_h / n_h. The random seed is in configs/reference.yaml; the frame and its baseline run id are in
data/reference/sampling_frame.meta.json.

## Estimation (provisional, see scripts/summarize_reference_dataset.py)
Stratified estimator of the number of loss chips with a normal-approximation interval. Assumptions: simple random
sampling inside strata; uncertain and ignored chips are missing at random within their stratum (probably not true);
strata whose labels are all equal have understated variance.

## Recall warning
Loss is probably rare among unflagged chips. With a few dozen unflagged chips per split the recall interval will be
wide. Say so; do not present recall as precise. The near_miss stratum is there to find missed loss more efficiently.

## CONFIRM before labelling
- Allocation per stratum and the total number of chips you can really label: ______
- Baseline run id the frame came from (printed by build_sampling_frame.py): ______
- Whether the reflectance check (check_reflectance.py) was clean before the frame was built: ______
