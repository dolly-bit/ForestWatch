# Spatial split design

- The split was created in Phase 1 (scripts/make_split_manifest.py) and is FROZEN with a checksum
  (data/labels/split_manifest.sha256). Phase 2 imports it unchanged (scripts/create_spatial_blocks.py); it does not
  re-randomise. data/splits/frozen.json records the checksum and a hash of the test block ids.
- Blocks: square blocks of block_size_px; splits are assigned to contiguous groups of group_blocks x group_blocks
  blocks (grouped random assignment, seed in configs/aravalli.yaml); train blocks touching validation/test blocks are
  dropped as `buffer` blocks. Every block belongs to exactly one split; chips never straddle two blocks.
- Regions (N/S x W/E halves of the block grid) are recorded so results can be reported by sub-area.
- Test labels are created last and are not used for development.

## Known limitations of the split
- One study area and one before/after pair: no independent geography.
- The buffer protects train from validation/test, but validation and test blocks may touch each other, so they are
  not fully spatially independent. Report this; for the final evaluation prefer test blocks that do not neighbour validation blocks.
- Block counts per split: CONFIRM from data/splits/frozen.json: train ___ validation ___ test ___ buffer ___
