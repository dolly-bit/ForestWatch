# Review summary (candidate level)

> These are reviewer verdict statistics on a sample of candidate detections. They are not validated pixel-level precision or recall, and they cannot show how much real vegetation loss was missed.

## Input and validation
- File: `data/labels/review_v2.csv`
- SHA-256: `6a58938fbb7c7a6d20744716c53741b9a18cd505375fe6c1c8844e5d39597a36`
- Rows: 60 | unique ids: 60 | duplicate ids: 0
- Missing columns: none

### Warnings
- none

## Sampling (from review_meta.json)
- Frame: 4150 candidates in total, 1328 eligible (area >= 0.3 ha)
- Sample: 60 drawn uniformly without replacement, seed 0; not stratified
- The seasonal filter flag was computed after sampling (sampling was done before filtering)

## Verdicts, all rows
- Rows: 60 | y: 0 | n: 0 | ?: 0 | unreviewed: 60 | invalid: 0
- Decided cases (y + n): 0
- Positive-verdict rate among decided: **undefined**

## By `landcover_name`
_Post-hoc subgroups of one sample (not pre-defined strata); small groups are imprecise._

### bare/sparse
- Rows: 1 | y: 0 | n: 0 | ?: 0 | unreviewed: 1 | invalid: 0
- Decided cases (y + n): 0
- Positive-verdict rate among decided: **undefined**
- WARNING: fewer than 10 decided cases; treat as anecdotal

### built-up
- Rows: 5 | y: 0 | n: 0 | ?: 0 | unreviewed: 5 | invalid: 0
- Decided cases (y + n): 0
- Positive-verdict rate among decided: **undefined**
- WARNING: fewer than 10 decided cases; treat as anecdotal

### cropland
- Rows: 44 | y: 0 | n: 0 | ?: 0 | unreviewed: 44 | invalid: 0
- Decided cases (y + n): 0
- Positive-verdict rate among decided: **undefined**
- WARNING: fewer than 10 decided cases; treat as anecdotal

### grassland
- Rows: 4 | y: 0 | n: 0 | ?: 0 | unreviewed: 4 | invalid: 0
- Decided cases (y + n): 0
- Positive-verdict rate among decided: **undefined**
- WARNING: fewer than 10 decided cases; treat as anecdotal

### shrubland
- Rows: 2 | y: 0 | n: 0 | ?: 0 | unreviewed: 2 | invalid: 0
- Decided cases (y + n): 0
- Positive-verdict rate among decided: **undefined**
- WARNING: fewer than 10 decided cases; treat as anecdotal

### tree cover
- Rows: 4 | y: 0 | n: 0 | ?: 0 | unreviewed: 4 | invalid: 0
- Decided cases (y + n): 0
- Positive-verdict rate among decided: **undefined**
- WARNING: fewer than 10 decided cases; treat as anecdotal

## Not available from this file
- Recall (needs reference loss areas including places the detector did not flag)
- Pixel-level precision, F1, IoU, false alarms per 100 km2 (need aligned reference masks)
