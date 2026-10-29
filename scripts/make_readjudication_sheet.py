"""Create a BLIND, shuffled sheet to re-check the 60 reviewed locations (no NDVI, no filter flag, no old verdict).

  python scripts/make_readjudication_sheet.py
Then open data/labels/readjudication.csv in Excel and, for each row, click maps_link and fill:
  change_type : natural_vegetation_loss | crop_cycle_or_field_change | construction_or_road | mining_or_quarry |
                other_bare_ground | no_visible_change | cannot_tell
  verdict_v2  : y = permanent loss of vegetation (natural vegetation cleared, construction, mining, other bare ground)
                n = no visible change, or a seasonal crop / field change     ? = cannot tell
  confidence  : high / low   evidence_date_seen: the date shown for the imagery, if visible   notes: anything useful
Never overwrites an existing sheet. Do not look at your old verdicts while filling it in.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.review_summary import read_review_csv
from forestwatch.readjudication import make_blank_sheet, write_csv, BLANK_COLUMNS

ROOT = Path(__file__).resolve().parents[1]
src = ROOT / "data" / "labels" / "review_v1_original.csv"
if not src.exists():
    src = ROOT / "outputs" / "review" / "review.csv"
rows, _ = read_review_csv(src)
sheet = make_blank_sheet(rows, seed=1)
out = ROOT / "data" / "labels" / "readjudication.csv"
try:
    write_csv(out, sheet, BLANK_COLUMNS)
except FileExistsError as e:
    sys.exit(str(e))
print(f"Wrote {len(sheet)} blank rows (shuffled) to {out}\nSource ids from: {src}\n{__doc__}")
