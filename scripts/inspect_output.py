import glob
import json
from app.services.pdf_extractor import extract_text_from_pdf
from app.services.invoice_parser import parse_invoice_text

folder = "/home/chaitany/Desktop/sample-invoices/samples/*.pdf"
files = sorted(glob.glob(folder))

print(f"{'FILE':<35} | {'VENDOR':<30} | {'DATE':<12} | {'TOTAL':<12} | {'GSTIN'}")
print("-" * 120)

for file in files:
    filename = file.split("/")[-1][:33]
    text = extract_text_from_pdf(file)

    # We pass use_llm=False to guarantee we are only testing the regex
    parsed = parse_invoice_text(text, use_llm=False, tables=[])

    vendor = (parsed.get("vendor_name") or "None")[:28]
    date = parsed.get("date") or "None"
    total = parsed.get("total") or "None"
    gstin = parsed.get("gstin") or "None"

    print(f"{filename:<35} | {vendor:<30} | {date:<12} | {total:<12} | {gstin}")
