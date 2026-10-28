# Sampling protocol for the candidate review

Facts below come from the code that made the sheet (scripts/make_review.py -> forestwatch.review.build_review).
Exact numbers are in outputs/review/review_meta.json and in review_summary.md. Items marked CONFIRM need your answer.

## Population (sampling frame)
- Population: connected areas (8-connectivity) of the NDVI-baseline detection mask computed WITHOUT the seasonal
  persistence filter, from the stacks and configs/aravalli.yaml in use at the time.
- Eligibility: area >= `min_area_ha` (default 0.3 ha in make_review.py). Smaller candidates had no chance of selection,
  so nothing here says anything about candidates below that size.
- Total candidates / eligible candidates / sample size / seed: see review_meta.json (copied into review_summary.md).
- CONFIRM: review_meta.json belongs to the same run as review.csv (python scripts/verify_baseline.py prints PASS).

## Method
- Simple random sampling without replacement of `n` candidate ids using numpy `default_rng(seed)`; not stratified by
  area, location or seasonal-filter status.
- The seasonal filter was applied AFTER sampling to give each sampled candidate a `kept_by_seasonal` flag
  (yes if at least half of its pixels survive the filter). Subgroup results by this flag are post-hoc.
- Sheet layout: sorted by id, 5 candidates per page.

## Provenance and exceptions
- Generated on: CONFIRM (file time of review_meta.json: ______ )
- CONFIRM: no candidate was skipped, replaced or added by hand. (If any was, list ids and reasons here.)
- CONFIRM: make_review.py was run once for this sheet (re-running overwrote earlier sheets before the overwrite guard existed).
- Reviewer knowledge while labelling: NOT blind. The page titles showed the NDVI change ("greenness before -> after")
  and the seasonal-filter status (KEPT/removed), and the CSV contained mean_ndvi_drop and kept_by_seasonal.

## What this sample can support
- An estimate of the share of eligible (>= min area) candidates that the reviewer judged to be real vegetation loss,
  with a sampling interval, under the assumptions in review_summary.md.
- It cannot support recall, pixel-level metrics or claims about smaller candidates.
