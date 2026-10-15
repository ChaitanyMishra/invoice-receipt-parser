import time
import sys
from pathlib import Path

from app.services.pdf_extractor import extract_text_from_pdf
from app.services.invoice_parser import parse_invoice_text

def measure_one(pdf_path: str):
    # 1. Extract text — time it
    t0 = time.time()
    text = extract_text_from_pdf(pdf_path)
    t1 = time.time()

    if not text:
        print(f"{pdf_path}: no text extracted")
        return

    # 2. Parse — time it
    t2 = time.time()
    parsed = parse_invoice_text(text)
    t3 = time.time()

    # 3. Report
    print(f"\n{pdf_path}")
    print(f"  text length: {len(text)}")
    print(f"  extraction: {t1-t0:.2f}s")
    print(f"  parsing: {t3-t2:.2f}s")
    print(f"  total: {t3-t0:.2f}s")
    print(f"  parsed:")
    for k, v in parsed.items():
        if k != "line_items":
            print(f"    {k}: {v}")
    print(f"    line_items: {len(parsed.get('line_items', []))} items")

if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "sample-invoices/Invoices/APR"
    pdfs = list(Path(folder).glob("*.pdf"))

    print(f"Found {len(pdfs)} PDFs in {folder}")
    for pdf in pdfs[:5]:   # limit to 5 to save API quota
        measure_one(str(pdf))
