"""Draw the stratified random sample for one split and create the BLIND label sheet + a KML for Google Earth.
  python scripts/select_reference_units.py --split validation --reviewer R1
Label the validation split first; label the test split last, once, after the protocol is final."""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.reference.context import load_context
from forestwatch.reference.schema import read_rows, write_rows, SELECTED_COLUMNS, SHEET_COLUMNS, SPLITS
from forestwatch.reference.sampling import sample_split
from forestwatch.reference.labels import make_label_sheet
from forestwatch.reference.export import to_kml

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--split", required=True, choices=SPLITS)
ap.add_argument("--reviewer", required=True, help="an id for you, e.g. R1")
args = ap.parse_args()
cfg, ref, meta, shape = load_context(ROOT)
per = ref["allocation"][args.split]
if per <= 0:
    sys.exit(f"allocation for {args.split} is 0 in configs/reference.yaml")
frame = read_rows(ROOT / "data" / "reference" / "sampling_frame.csv")
chosen = sample_split(frame, args.split, per, ref["seed"])
d = ROOT / "data" / "reference"
kml = d / f"chips_{args.split}.kml"
outputs = [d / f"selected_units_{args.split}.csv", d / f"label_sheet_{args.split}.csv", kml]
if any(p.exists() for p in outputs):
    sys.exit("Already exists, refusing to overwrite (the selection defines inclusion probabilities): "
             + ", ".join(p.name for p in outputs if p.exists()))
write_rows(outputs[0], chosen, SELECTED_COLUMNS)
sheet = make_label_sheet(chosen, tuple(meta["transform"]), meta["crs"], args.reviewer)
write_rows(outputs[1], sheet, SHEET_COLUMNS)
kml.write_text(to_kml(chosen, tuple(meta["transform"]), meta["crs"], f"ForestWatch {args.split} chips"), encoding="utf-8")
print(f"Selected {len(chosen)} chips for {args.split}. Files in data/reference: selected_units_{args.split}.csv (do NOT open while labelling), "
      f"label_sheet_{args.split}.csv, chips_{args.split}.kml")
print("Labelling: import the KML in Google Earth (earth.google.com/web > Projects > Import KML file) to see each square on high-resolution "
      "imagery, or use maps_link in the sheet. Read reports/phase2/reference_labeling_protocol.md first.")
