from pathlib import Path
import json

from src.pipeline import process_pdf


DOCUMENTS_DIR = Path("documents")
OUTPUT_DIR = Path("output")


def main():

    OUTPUT_DIR.mkdir(exist_ok=True)

    pdf_files = sorted(DOCUMENTS_DIR.glob("*.pdf"))

    print("=" * 70)
    print("BOOKABLE PAYABLE PIPELINE")
    print("=" * 70)

    print(f"\nFound {len(pdf_files)} PDF files.")

    successful = 0
    declined = 0
    failed = 0

    for i, pdf_path in enumerate(pdf_files, start=1):

        print(f"\n[{i}/{len(pdf_files)}] Processing {pdf_path.name}")

        try:

            result = process_pdf(pdf_path)

            output_file = OUTPUT_DIR / f"{pdf_path.stem}.json"

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(
                    result,
                    f,
                    indent=2,
                    ensure_ascii=False
                )

            if result["payables"]:
                successful += 1
                print("  → PAYABLE")

            else:
                declined += 1
                print("  → DECLINED")

            print(f"  → Saved: {output_file}")

        except Exception as e:

            failed += 1

            print(f"  → ERROR: {e}")

            error_result = {
                "file": pdf_path.name,
                "payables": [],
                "declined": [
                    {
                        "doc_type": "PROCESSING_ERROR",
                        "reason": str(e)
                    }
                ]
            }

            output_file = OUTPUT_DIR / f"{pdf_path.stem}.json"

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(
                    error_result,
                    f,
                    indent=2
                )

    print("\n" + "=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)

    print(f"Total PDFs : {len(pdf_files)}")
    print(f"Payables   : {successful}")
    print(f"Declined   : {declined}")
    print(f"Errors     : {failed}")
    print(f"Output dir : {OUTPUT_DIR}")


if __name__ == "__main__":
    main()