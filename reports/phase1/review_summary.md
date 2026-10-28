# Review summary (candidate level)

> These are reviewer verdict statistics on a sample of candidate detections. They are not validated pixel-level precision or recall, and they cannot show how much real vegetation loss was missed.

## Input and validation
- File: `C:\Users\dolly_\Desktop\Projects\forestwatch\outputs\review\review.csv`
- SHA-256: `eca93c481bc02714ba1ec2c88c4a336781728a98f36ceb58d7791aeaf567b360`
- Rows: 60 | unique ids: 60 | duplicate ids: 0
- Missing columns: none

### Warnings
- none

## Sampling (from review_meta.json)
- Frame: 4150 candidates in total, 1328 eligible (area >= 0.3 ha)
- Sample: 60 drawn uniformly without replacement, seed 0; not stratified
- The seasonal filter flag was computed after sampling (sampling was done before filtering)

## Verdicts, all rows
- Rows: 60 | y: 44 | n: 14 | ?: 2 | unreviewed: 0 | invalid: 0
- Decided cases (y + n): 58
- Positive-verdict rate among decided: **75.9%**
- 95% Wilson interval: 63.5% to 85.0%
- If every '?' were negative: 73.3%; if every '?' were positive: 76.7%

## By `kept_by_seasonal`
_Post-hoc subgroups of one sample (not pre-defined strata); small groups are imprecise._

### no
- Rows: 7 | y: 5 | n: 2 | ?: 0 | unreviewed: 0 | invalid: 0
- Decided cases (y + n): 7
- Positive-verdict rate among decided: **71.4%**
- 95% Wilson interval: 35.9% to 91.8%
- If every '?' were negative: 71.4%; if every '?' were positive: 71.4%
- WARNING: fewer than 10 decided cases; treat as anecdotal

### yes
- Rows: 53 | y: 39 | n: 12 | ?: 2 | unreviewed: 0 | invalid: 0
- Decided cases (y + n): 51
- Positive-verdict rate among decided: **76.5%**
- 95% Wilson interval: 63.2% to 86.0%
- If every '?' were negative: 73.6%; if every '?' were positive: 77.4%

## Extrapolation to the sampling frame (provisional)
- Population 1328; sampled 58 decided (4.4%); finite-population factor 0.978
- Expected positive candidates: 1007 (95%: 843 to 1129)
- Assumptions: simple random sample from the stated population; reviewer verdicts treated as truth; '?' and unreviewed rows excluded; Wilson interval not adjusted for finite population

## Not available from this file
- Recall (needs reference loss areas including places the detector did not flag)
- Pixel-level precision, F1, IoU, false alarms per 100 km2 (need aligned reference masks)
