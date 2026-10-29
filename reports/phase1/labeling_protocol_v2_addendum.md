# Labeling protocol - v2 addendum (blind second look)

Paste or append this to labeling_protocol.md. It RESOLVES the open decision there.

## Why v2
The land-cover breakdown of the first review showed that 43 of 58 judged detections lie on land that ESA WorldCover
2021 classes as cropland, and only 6 on tree cover or shrubland. A single yes/no ("real") was not specific enough
to say what kind of change was real. The first review was also not blind (NDVI numbers and filter status were visible).

## Method
- scripts/make_readjudication_sheet.py creates data/labels/readjudication.csv: the same 60 locations, SHUFFLED,
  showing only id, lat, lon, maps_link and area. No NDVI values, no seasonal flag, no earlier verdict.
- The reviewer does not open the earlier verdicts while filling the sheet. Original verdicts are never edited.
- scripts/merge_readjudication.py joins the answers with the original sheet and the land-cover class
  (data/labels/review_v2.csv). Land cover is looked up AFTER labelling, so it cannot influence the answers.

## Fields
- change_type (what is visible at the location): natural_vegetation_loss, crop_cycle_or_field_change,
  construction_or_road, mining_or_quarry, other_bare_ground, no_visible_change, cannot_tell.
- verdict_v2: y = permanent loss of vegetation (natural vegetation cleared, construction/road, mining, other bare
  ground); n = no visible change or a seasonal crop / field change; ? = cannot tell. Same evidence rules as v1.
- confidence (high / low), evidence_date_seen (date shown for the imagery, if visible), notes.

## Reporting rules
- Report v2 results by land cover and by change_type, never as one headline number only.
- Claims about natural-vegetation or forest loss may use ONLY rows with change_type = natural_vegetation_loss, and
  must state how few such rows exist (with the interval).
- The 60-row sample has now been used for exploration and cannot be used to tune the detector. Any detector
  change is developed on train/validation blocks only (data/labels/split_manifest.csv, frozen) with new labels.
- One reviewer, imagery of unknown date: unchanged limitations (see known_limitations.md).
