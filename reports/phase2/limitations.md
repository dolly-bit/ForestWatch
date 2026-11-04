# Limitations of the reference dataset (Phase 2)

Update this as the dataset grows. CONFIRM items need your answer.

- Labels are visual interpretations by one reviewer (novice) of imagery whose dates are often unknown; no second reviewer.
  A blind re-review subset measures consistency but not correctness.
- The unit is a 320 m chip; the label does not say where in the chip the loss is. No pixel-level truth.
- The sampling frame depends on the baseline (flagged / near_miss / quiet) and on WorldCover 2021 land-cover groups,
  both imperfect. If the baseline or the reflectance scaling changes, the frame and the weights must be rebuilt.
- Recall will be imprecise because loss is rare among unflagged chips.
- Uncertain/ignored chips are excluded; if they differ systematically from decided chips, estimates are biased.
- One area, one pair of date windows; no evidence about other regions or years.
- Phase 1 reviews (v1, v2) were exploratory and are not part of this dataset.
- Reflectance check status when the frame was built: CONFIRM ______
- Protocol decisions that change results: field-to-building conversion counted as no_loss (CONFIRM), minimum 0.3 ha.
