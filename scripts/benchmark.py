import sys
import time
from pathlib import Path

from app.services.pdf_extractor import extract_text_from_pdf
from app.services.invoice_parser import parse_invoice_text


def benchmark_one(pdf_path: str) -> dict:
    """Process one PDF, return timing + results."""
    t0 = time.time()
    text = extract_text_from_pdf(pdf_path)
    t1 = time.time()

    if not text:
        return {
            "file": pdf_path,
            "extract_time": t1 - t0,
            "parse_time": 0,
            "invoice_number": None,
            "total": None,
            "tax_amount": None,
            "line_items": 0,
            "error": "no text extracted",
        }

    t2 = time.time()
    parsed = parse_invoice_text(text)
    t3 = time.time()

    return {
        "file": pdf_path,
        "extract_time": t1 - t0,
        "parse_time": t3 - t2,
        "invoice_number": parsed.get("invoice_number"),
        "total": parsed.get("total"),
        "tax_amount": parsed.get("tax_amount"),
        "line_items": len(parsed.get("line_items", [])),
        "error": None,
    }


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "test_data/invoices/APR"
    pdfs = sorted(Path(folder).rglob("*.pdf"))

    print(f"Found {len(pdfs)} PDFs in {folder}")
    print("=" * 80)

    results = []
    for pdf in pdfs:
        result = benchmark_one(str(pdf))
        results.append(result)

        print(f"\n{Path(result['file']).name}")
        print(f"  extract: {result['extract_time']:.2f}s")
        print(f"  parse:   {result['parse_time']:.2f}s")
        if result["error"]:
            print(f"  ERROR:   {result['error']}")
        else:
            print(f"  invoice_number: {result['invoice_number']}")
            print(f"  total:          {result['total']}")
            print(f"  tax_amount:     {result['tax_amount']}")
            print(f"  line_items:     {result['line_items']}")

    # Summary
    total_extract = sum(r["extract_time"] for r in results)
    total_parse = sum(r["parse_time"] for r in results)
    errors = sum(1 for r in results if r["error"])

    print("\n" + "=" * 80)
    print(f"SUMMARY")
    print(f"  Files:            {len(results)}")
    print(f"  Errors:           {errors}")
    print(f"  Total extract:    {total_extract:.2f}s")
    print(f"  Total parse:      {total_parse:.2f}s")
    print(f"  Avg per file:     {(total_extract + total_parse) / len(results):.2f}s")


if __name__ == "__main__":
    main()
