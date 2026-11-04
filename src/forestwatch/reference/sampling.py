"""Stratified random selection with known inclusion probabilities, and the matching estimator."""
from __future__ import annotations
import math
import zlib
import numpy as np

SPLIT_INDEX = {"train": 0, "validation": 1, "test": 2}
METHOD = "stratified_srs_without_replacement"


def sample_split(frame_rows, split: str, per_stratum: int, seed: int) -> list[dict]:
    """Simple random sample without replacement inside each stratum of the eligible chips of one split.
    selection_probability = n_h / N_h is exact (not estimated); sampling_weight = its inverse."""
    pools: dict = {}
    for r in frame_rows:
        if r["split"] == split and r["eligible"] == "yes":
            pools.setdefault(r["stratum"], []).append(r)
    out = []
    for stratum in sorted(pools):
        pool = sorted(pools[stratum], key=lambda r: r["unit_id"])
        N, n = len(pool), min(per_stratum, len(pool))
        if n <= 0:
            continue
        rng = np.random.default_rng([seed, SPLIT_INDEX[split], zlib.crc32(stratum.encode())])
        for i in sorted(rng.choice(N, size=n, replace=False)):
            out.append({**pool[int(i)], "selection_method": METHOD, "selection_probability": round(n / N, 6),
                        "sampling_weight": round(N / n, 6), "stratum_population": N, "stratum_sample": n})
    return out


def stratified_estimate(units) -> dict:
    """Estimate how many chips in the frame are 'loss' (and the prevalence) from a stratified sample.

    units: dicts with stratum, y (1 loss / 0 no_loss), N (stratum population). Units whose label is
    uncertain/ignore must be left out by the caller; the estimate then ASSUMES they are missing at random
    within their stratum, which may be false. Normal-approximation interval; strata with n < 2 use the worst
    case p = 0.5; strata with all-equal labels have zero estimated variance, which understates real uncertainty."""
    by: dict = {}
    for u in units:
        by.setdefault(u["stratum"], {"N": u["N"], "y": []})["y"].append(u["y"])
    total_pop = sum(g["N"] for g in by.values())
    total, var, notes, rows = 0.0, 0.0, [], []
    for s, g in sorted(by.items()):
        n, N = len(g["y"]), g["N"]
        p = sum(g["y"]) / n
        total += N * p
        if n >= N:
            v = 0.0
        elif n < 2:
            v = N ** 2 * (1 - n / N) * 0.25
            notes.append(f"{s}: only {n} labelled chip(s); worst-case variance used")
        else:
            v = N ** 2 * (1 - n / N) * p * (1 - p) / (n - 1)
            if p in (0.0, 1.0):
                notes.append(f"{s}: all {n} labels equal; its variance is understated")
        var += v
        rows.append({"stratum": s, "N": N, "n_labelled": n, "loss_share": p})
    se = math.sqrt(var)
    return {"estimated_loss_chips": total, "se": se, "ci95": [max(0.0, total - 1.96 * se), total + 1.96 * se],
            "population_chips": total_pop, "prevalence": total / total_pop if total_pop else None,
            "strata": rows, "notes": notes}
