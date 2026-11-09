import math
import numpy as np
import pytest

from forestwatch.manifest import build_manifest
from forestwatch.reference.blocks import prepare_blocks, check_blocks, hash_of_test_blocks, blocks_geojson, region_for
from forestwatch.reference.frame import build_frame, stratum_table, landcover_group
from forestwatch.reference.sampling import sample_split, stratified_estimate
from _phase2_helpers import (make_frame, SPLIT_CFG, META, SHAPE, ref_cfg, WithPyproj)


def test_blocks_import_unchanged_and_spatially_independent():
    manifest = build_manifest(SPLIT_CFG, META, "t")
    blocks = prepare_blocks(manifest, 10.0, SHAPE)
    assert check_blocks(blocks) == [] and len(blocks) == 16
    assert {b["split"] for b in blocks} <= {"train", "validation", "test", "buffer"}
    assert blocks[0]["area_km2"] == round(64 * 64 * 100 / 1e6, 4) and blocks[0]["region"] == "NW"
    assert hash_of_test_blocks(blocks) == hash_of_test_blocks(prepare_blocks(manifest, 10.0, SHAPE))
    dup = blocks + [dict(blocks[0], split="test")]                         # one block in two splits must be caught
    assert any("more than once" in p for p in check_blocks(dup))
    assert check_blocks([dict(blocks[0], split="holdout")])
    assert [region_for(0, 0, 4, 4), region_for(3, 3, 4, 4), region_for(0, 3, 4, 4), region_for(3, 0, 4, 4)] == ["NW", "SE", "NE", "SW"]
    with WithPyproj():
        gj = blocks_geojson(blocks)
    assert len(gj["features"]) == 16 and gj["features"][0]["geometry"]["coordinates"][0][0] == gj["features"][0]["geometry"]["coordinates"][0][-1]


def test_frame_covers_the_grid_and_excludes_buffer_and_unobserved_chips():
    rows, manifest = make_frame()
    assert len(rows) == 64 and len({r["unit_id"] for r in rows}) == 64
    assert all(r["chip_row1"] - r["chip_row0"] == 32 for r in rows)
    reasons = {r["unit_id"]: r["exclusion_reason"] for r in rows}
    assert reasons["C000_000"] == "poor_observation"
    assert {r["exclusion_reason"] for r in rows if r["split"] == "buffer"} <= {"buffer_block"}
    assert all(r["eligible"] == "no" for r in rows if r["split"] == "buffer")
    statuses = {r["baseline_status"] for r in rows}
    assert "flagged" in statuses and "unflagged_quiet" in statuses
    tab = stratum_table(rows)
    assert "buffer" not in tab and all(isinstance(n, int) and n > 0 for t in tab.values() for n in t.values())
    with pytest.raises(ValueError):
        build_frame(SHAPE, 48, 64, manifest, np.zeros(SHAPE, bool), np.zeros(SHAPE), np.ones(SHAPE, bool),
                    np.zeros(SHAPE, "uint8"), ref_cfg(), ref_cfg()["landcover_groups"])          # 48 does not divide 64
    with pytest.raises(ValueError):
        build_frame(SHAPE, 32, 64, manifest, np.zeros((10, 10), bool), np.zeros(SHAPE), np.ones(SHAPE, bool),
                    np.zeros(SHAPE, "uint8"), ref_cfg(), ref_cfg()["landcover_groups"])           # grids do not match
    assert [landcover_group(c, ref_cfg()["landcover_groups"]) for c in (10, 40, 50, 60, 80)] == ["natural", "cropland", "built_up", "other", "other"]


def test_sampling_is_deterministic_probabilistic_and_only_from_eligible_chips():
    rows, _ = make_frame()
    a, b = sample_split(rows, "validation", 3, 2026), sample_split(rows, "validation", 3, 2026)
    assert a == b and a
    assert sample_split(rows, "validation", 3, 2027) != a or len(a) <= 3
    elig = {r["unit_id"] for r in rows if r["eligible"] == "yes" and r["split"] == "validation"}
    assert {r["unit_id"] for r in a} <= elig
    by = {}
    for r in a:
        by.setdefault(r["stratum"], []).append(r)
    for s, units in by.items():
        N = sum(1 for r in rows if r["eligible"] == "yes" and r["split"] == "validation" and r["stratum"] == s)
        n = min(3, N)
        assert len(units) == n and all(abs(u["selection_probability"] - n / N) < 1e-5 for u in units)
        assert all(abs(u["sampling_weight"] - N / n) < 1e-4 and u["stratum_population"] == N for u in units)
        assert len({u["unit_id"] for u in units}) == n                       # without replacement
    assert sample_split(rows, "validation", 0, 1) == []
    everything = sample_split(rows, "test", 10_000, 1)                       # larger than every stratum: take all, probability 1
    assert all(u["selection_probability"] == 1.0 for u in everything)


def test_stratified_estimator_known_values():
    units = ([{"stratum": "A", "y": 1, "N": 100}] * 3 + [{"stratum": "A", "y": 0, "N": 100}] * 7
             + [{"stratum": "B", "y": 0, "N": 50}] * 5)
    e = stratified_estimate(units)
    assert abs(e["estimated_loss_chips"] - 30.0) < 1e-9
    assert abs(e["se"] - math.sqrt(100 ** 2 * 0.9 * 0.3 * 0.7 / 9)) < 1e-9
    assert e["population_chips"] == 150 and abs(e["prevalence"] - 0.2) < 1e-9
    assert any("all 5 labels equal" in n for n in e["notes"])
    assert e["ci95"][0] >= 0
    full = stratified_estimate([{"stratum": "C", "y": 1, "N": 2}, {"stratum": "C", "y": 0, "N": 2}])
    assert full["estimated_loss_chips"] == 1.0 and full["se"] == 0.0           # fully sampled stratum: no sampling error
    single = stratified_estimate([{"stratum": "D", "y": 1, "N": 40}])
    assert single["se"] > 0 and any("worst-case" in n for n in single["notes"])


def test_allocation_can_differ_by_stratum_with_clear_precedence():
    from forestwatch.reference.sampling import allocation_for
    spec = {"default": 4, "*|natural": 10, "*|cropland": 5, "flagged|*": 7, "flagged|natural": 12}
    assert allocation_for(3, "anything|else") == 3                                   # a plain number still works
    assert allocation_for(spec, "flagged|natural") == 12                             # exact name wins
    assert allocation_for(spec, "unflagged_quiet|natural") == 10                     # then '*|group'
    assert allocation_for(spec, "flagged|cropland") == 5                             # '*|group' beats 'status|*'
    assert allocation_for(spec, "flagged|built_up") == 7                             # then 'status|*'
    assert allocation_for(spec, "unflagged_quiet|built_up") == 4                     # then default
    assert allocation_for({"*|natural": 2}, "unflagged_quiet|built_up") == 0         # no default: nothing drawn
    with pytest.raises(ValueError):
        allocation_for({"default": -1}, "x|y")


def test_sampling_follows_a_per_stratum_allocation_and_keeps_exact_probabilities():
    rows, _ = make_frame()
    spec = {"default": 1, "*|natural": 3}
    a = sample_split(rows, "validation", spec, 2026)
    assert a == sample_split(rows, "validation", spec, 2026)
    pops = {}
    for r in rows:
        if r["split"] == "validation" and r["eligible"] == "yes":
            pops[r["stratum"]] = pops.get(r["stratum"], 0) + 1
    counts = {}
    for u in a:
        counts[u["stratum"]] = counts.get(u["stratum"], 0) + 1
    for s, N in pops.items():
        want = min(3 if s.endswith("|natural") else 1, N)
        assert counts.get(s, 0) == want, (s, counts.get(s), want)
        assert all(abs(u["selection_probability"] - want / N) < 1e-5 for u in a if u["stratum"] == s)
