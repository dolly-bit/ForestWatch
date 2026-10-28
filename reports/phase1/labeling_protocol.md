# Labeling protocol (written to match how the sheet was actually labelled)

Items marked CONFIRM need your answer. Do not edit the original verdicts; record changes in
data/labels/review_annotations.csv (candidate_id, reviewer, review_date, verdict, confidence, evidence_source,
evidence_date, notes).

## Evidence used
- Primary: Google Maps satellite imagery opened from each row's `maps_link`. Acquisition date of that imagery:
  UNKNOWN (it may not match the before/after windows). CONFIRM: any other source used (e.g. Google Earth history).
- Secondary: the review page pictures (NDVI "greenness" before/after and outline), made from the same Sentinel-2
  data that produced the detections. These are NOT independent of the detector.
- Reviewers: one person. CONFIRM name and experience: novice in image interpretation (initially found images hard
  to tell apart). No second reviewer or adjudication.

## Verdicts
- `y`: the satellite photo at the candidate location shows bare or cleared ground (for example quarry or mining,
  new road or building plot, freshly cleared patch) where the area is otherwise vegetated / was vegetated before.
- `n`: the location still shows vegetation, looks the same as its surroundings, or is an agricultural field
  (crop cycle, not vegetation loss in the sense of this project), or the detection looks like an artefact.
- `?`: cannot decide, or the photo looks older than the change window. Never counted as y or n.
- Typed values must be exactly y, n or ?. The summary script reports anything else as a warning.

## OPEN DECISION: what counts as the positive class (resolve before Phase 2)
The sheet was labelled with an informal rule ("bare/cleared ground = y, farmland = n"). Later analysis found that
about three quarters of the reviewed detections lie on land that ESA WorldCover 2021 classes as cropland, and
34 of the 44 'y' verdicts were among them. So some 'y' verdicts may be cleared or bare FARMLAND or plots rather than
tree or scrub loss. Choose one definition and write it here:
  [ ] A. any vegetation loss to bare/built ground (includes farmland converted to plots)
  [ ] B. tree or scrub loss only (requires evidence that woody vegetation was present before)
Then re-adjudicate the ambiguous 'y' rows (start with the cropland-class ones) and store the new verdicts in
review_annotations.csv with evidence notes; keep the original column unchanged.

## Distinguishing vegetation loss from other changes (CONFIRM each rule as you applied it)
- Seasonal drying: ______   - Fire/burn scar: ______   - Cloud/shadow: ______
- Construction: ______      - Agriculture: n (see above)   - Image artefact: ______
