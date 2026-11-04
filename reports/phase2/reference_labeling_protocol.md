# Reference labeling protocol - version 1.0

Items marked CONFIRM need your decision BEFORE the first label. Changing a definition later means a new protocol
version and relabelling (change `protocol_version` in configs/reference.yaml).

## 1. Target event
Observable, permanent loss of natural or semi-natural vegetation (trees, shrubs, scrub, grass) inside the chip,
converted to bare ground, a built surface (building, road, plot) or a mine/quarry, between the comparison windows,
covering at least 0.3 ha (about 55 m x 55 m, 30 pixels) within the chip.
This is observable vegetation loss, NOT proof of illegal deforestation or of forest loss in a legal sense.

Out of scope (label `no_loss` and write what you saw in notes): seasonal or crop-cycle changes in farm fields,
harvest, ploughing, fallow; irrigated crops turning bare.
CONFIRM: conversion of an agricultural field to buildings is `no_loss` under v1.0 (it is not natural vegetation).
If you want it counted, decide now and change the definition above.

## 2. Comparison windows
Before: CONFIRM (copy from configs/aravalli.yaml: ______ to ______)
After:  CONFIRM (______ to ______). Imagery of other dates may not show the change: lower confidence or use `uncertain`.

## 3. Classes
- `loss`: the target event is visible inside the chip. Fill `loss_type` (natural_to_bare, natural_to_built,
  natural_to_mining, other) and, if you can, event_start / event_end (YYYY-MM-DD, otherwise leave empty).
- `no_loss`: you looked at the whole chip and see no target event (unchanged vegetation, fields, existing buildings).
- `uncertain`: you cannot decide (blurry, shadows, imagery too old or too new, mixed). NEVER convert to `no_loss`.
  Uncertain chips are excluded from evaluation and reported separately.
- `ignore`: not assessable or out of scope (cloud over the chip, water only, no imagery).

## 4. How to review a chip (the unit is a 320 m square)
1. Import data/reference/chips_<split>.kml into Google Earth (earth.google.com/web > Projects > Import KML file).
   Each square is named by its unit id and drawn on high-resolution imagery. Google Earth Pro (desktop) also has a
   historical-imagery time slider. Alternative: the `maps_link` in the sheet, then judge the 320 m square around the pin.
2. Judge the WHOLE square, not just the centre. Look at it at two zoom levels.
3. Record the evidence: `evidence_source` (for example "Google Earth Pro historical imagery"),
   `evidence_before_date` and `evidence_after_date` (YYYY, YYYY-MM, YYYY-MM-DD or `unknown`).
4. `confidence`: high = clear and recent enough; medium = probably; low = guess-like. Prefer `uncertain` over a low-confidence guess.

## 5. Evidence rules
- Primary evidence: dated high-resolution imagery. Sentinel-2 composites may support but not decide (the detector
  uses the same data: using it alone would be circular).
- Do not use detector output, NDVI values or the sampling stratum to decide. The blind sheet shows none of them.
- Imagery of unknown date is allowed but must be recorded as `unknown`; it lowers confidence.

## 6. Process rules
- One reviewer so far. CONFIRM name/experience: ______ . Label validation first, test LAST and only once.
- Never open selected_units_<split>.csv or the sampling frame while labelling.
- Blind re-review of at least 20% of the chips after at least 7 days (scripts/rereview.py). Originals are never edited;
  adjudicated labels go in a separate file.
- Test labels are not used for development, tuning or threshold selection.
