# Review summary (candidate level)

> These are reviewer verdict statistics on a sample of candidate detections. They are not validated pixel-level precision or recall, and they cannot show how much real vegetation loss was missed.

## Input and validation
- File: `data/labels/review_v2.csv`
- SHA-256: `4b14daa6234d483633e86e32107b53608d7ff3261ed3f4b19dbf0e4df917e0ea`
- Rows: 60 | unique ids: 60 | duplicate ids: 0
- Missing columns: none

### Warnings
- none

## Sampling (from review_meta.json)
- Frame: 4150 candidates in total, 1328 eligible (area >= 0.3 ha)
- Sample: 60 drawn uniformly without replacement, seed 0; not stratified
- The seasonal filter flag was computed after sampling (sampling was done before filtering)

## Verdicts, all rows
- Rows: 60 | y: 23 | n: 36 | ?: 1 | unreviewed: 0 | invalid: 0
- Decided cases (y + n): 59
- Positive-verdict rate among decided: **39.0%**
- 95% Wilson interval: 27.6% to 51.7%
- If every '?' were negative: 38.3%; if every '?' were positive: 40.0%

## By `landcover_name`
_Post-hoc subgroups of one sample (not pre-defined strata); small groups are imprecise._

### bare/sparse
- Rows: 1 | y: 1 | n: 0 | ?: 0 | unreviewed: 0 | invalid: 0
- Decided cases (y + n): 1
- Positive-verdict rate among decided: **100.0%**
- 95% Wilson interval: 20.7% to 100.0%
- If every '?' were negative: 100.0%; if every '?' were positive: 100.0%
- WARNING: fewer than 10 decided cases; treat as anecdotal

### built-up
- Rows: 5 | y: 5 | n: 0 | ?: 0 | unreviewed: 0 | invalid: 0
- Decided cases (y + n): 5
- Positive-verdict rate among decided: **100.0%**
- 95% Wilson interval: 56.6% to 100.0%
- If every '?' were negative: 100.0%; if every '?' were positive: 100.0%
- WARNING: fewer than 10 decided cases; treat as anecdotal

### cropland
- Rows: 44 | y: 12 | n: 32 | ?: 0 | unreviewed: 0 | invalid: 0
- Decided cases (y + n): 44
- Positive-verdict rate among decided: **27.3%**
- 95% Wilson interval: 16.3% to 41.8%
- If every '?' were negative: 27.3%; if every '?' were positive: 27.3%

### grassland
- Rows: 4 | y: 2 | n: 2 | ?: 0 | unreviewed: 0 | invalid: 0
- Decided cases (y + n): 4
- Positive-verdict rate among decided: **50.0%**
- 95% Wilson interval: 15.0% to 85.0%
- If every '?' were negative: 50.0%; if every '?' were positive: 50.0%
- WARNING: fewer than 10 decided cases; treat as anecdotal

### shrubland
- Rows: 2 | y: 1 | n: 1 | ?: 0 | unreviewed: 0 | invalid: 0
- Decided cases (y + n): 2
- Positive-verdict rate among decided: **50.0%**
- 95% Wilson interval: 9.5% to 90.5%
- If every '?' were negative: 50.0%; if every '?' were positive: 50.0%
- WARNING: fewer than 10 decided cases; treat as anecdotal

### tree cover
- Rows: 4 | y: 2 | n: 1 | ?: 1 | unreviewed: 0 | invalid: 0
- Decided cases (y + n): 3
- Positive-verdict rate among decided: **66.7%**
- 95% Wilson interval: 20.8% to 93.9%
- If every '?' were negative: 50.0%; if every '?' were positive: 75.0%
- WARNING: fewer than 10 decided cases; treat as anecdotal

## Extrapolation to the sampling frame (provisional)
- Population 1328; sampled 59 decided (4.4%); finite-population factor 0.978
- Expected positive candidates: 518 (95%: 366 to 687)
- Assumptions: simple random sample from the stated population; reviewer verdicts treated as truth; '?' and unreviewed rows excluded; Wilson interval not adjusted for finite population

## Not available from this file
- Recall (needs reference loss areas including places the detector did not flag)
- Pixel-level precision, F1, IoU, false alarms per 100 km2 (need aligned reference masks)
