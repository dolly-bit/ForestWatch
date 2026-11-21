"""Label with dropdown menus in Excel, then write the answers back to the CSV the other scripts use.

  python scripts/label_workbook.py make    --split validation    -> data/reference/label_workbook_validation.xlsx
  (open it in Excel, fill the yellow columns on the Label sheet, save as .xlsx, close Excel)
  python scripts/label_workbook.py collect --split validation    -> checks your answers, updates label_sheet_validation.csv
then:  python scripts/ingest_labels.py --split validation
Needs:  pip install openpyxl"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.reference.context import load_context
from forestwatch.reference.schema import read_rows, write_rows, SHEET_COLUMNS, SPLITS
from forestwatch.reference.workbook import build_workbook, read_workbook, check_answers, apply_to_sheet

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("action", choices=["make", "collect"])
ap.add_argument("--split", required=True, choices=SPLITS)
ap.add_argument("--force", action="store_true")
args = ap.parse_args()
cfg, ref, meta, shape = load_context(ROOT)
d = ROOT / "data" / "reference"
csv_path, xlsx = d / f"label_sheet_{args.split}.csv", d / f"label_workbook_{args.split}.xlsx"
sheet = read_rows(csv_path)
if args.action == "make":
    try:
        build_workbook(sheet, xlsx, ref, overwrite=args.force)
    except FileExistsError as e:
        sys.exit(str(e))
    print(f"Created {xlsx}\nOpen it in Excel. Read the 'Guide' sheet, then fill the yellow columns on the 'Label' sheet.")
else:
    res = check_answers(read_workbook(xlsx), ref)
    for w in res["warnings"][:30]:
        print("WARNING:", w)
    if res["errors"]:
        for e in res["errors"][:40]:
            print("ERROR:  ", e)
        sys.exit(f"{len(res['errors'])} error(s): fix them in the workbook, save, and run collect again. Nothing was written.")
    already = sum(1 for r in sheet if (r.get("class_label") or "").strip())
    if already and not args.force:
        sys.exit(f"{csv_path.name} already contains {already} answers. Use --force to replace them with the workbook.")
    rows, problems = apply_to_sheet(sheet, read_workbook(xlsx))
    if problems:
        sys.exit("PROBLEMS:\n  " + "\n  ".join(problems))
    write_rows(csv_path, rows, SHEET_COLUMNS, overwrite=True)
    print(f"Updated {csv_path.name}: {len(rows) - len(res['unlabelled'])} labelled, {len(res['unlabelled'])} still empty "
          f"{res['unlabelled'][:6] if res['unlabelled'] else ''}\nNext: python scripts/ingest_labels.py --split {args.split}"
          + ("  (add --allow-partial if some chips stay empty)" if res["unlabelled"] else ""))
