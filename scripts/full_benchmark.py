import glob
import json
import os
import time

from app.services.pdf_extractor import extract_text_from_pdf
from app.services.invoice_parser import parse_invoice_text, extract_tables_from_pdf
FORCE_LLM = os.environ.get("FORCE_LLM") == "1"
folder = "/home/chaitany/Desktop/sample-invoices/samples/*.pdf"
files = glob.glob(folder)
files.sort()

# Fields we check for accuracy (only if expected.json exists)
check_fields = ["invoice_number", "date", "gstin", "total", "tax_amount"]

# expected.json sits in the same folder as this script.
# You must fill it BY HAND by reading the PDFs (not by copying parser output).
expected_path = os.path.join(os.path.dirname(__file__), "expected.json")
expected = {}
if os.path.exists(expected_path):
    with open(expected_path) as f:
        expected = json.load(f)
    print("expected.json found, accuracy will be checked.")
else:
    print("expected.json not found, accuracy will be skipped.")


def same_value(field, got, want):
    # got = what the parser found, want = the correct value
    if got is None or want is None:
        return False
    if field in ("total", "tax_amount"):
        try:
            return abs(float(got) - float(want)) < 0.01
        except ValueError:
            return False
    return str(got).strip().upper() == str(want).strip().upper()


print()
print(
    f"{'FILE':<34} | {'TEXT':<7} | {'TABLES':<7} | {'PARSE':<7} | {'TOTAL':<7} | STATUS"
)
print("-" * 95)

total_time = 0
regex_count = 0
llm_count = 0
regex_times = []
llm_times = []
fields_right = 0
fields_checked = 0

for file in files:
    filename = file.split("/")[-1]
    start = time.time()

    # 1. get the text
    t0 = time.time()
    text = extract_text_from_pdf(file)
    t_text = time.time() - t0

    # 2. get the tables (timed separately so we can see what it costs)
    t1 = time.time()
    tables = extract_tables_from_pdf(file)
    t_tables = time.time() - t1

    # 3. parse
    t2 = time.time()
    if text:
        parsed = parse_invoice_text(text, tables=tables, force_llm=FORCE_LLM)
    else:
        parsed = {}
    t_parse = time.time() - t2

    total = time.time() - start
    total_time += total

    # The REAL check: did the parser say it used the LLM?
    if not text:
        status = "NO TEXT"
    elif parsed.get("llm_used"):
        status = "LLM USED"
        llm_count += 1
        llm_times.append(total)
    else:
        status = "REGEX ONLY"
        regex_count += 1
        regex_times.append(total)

    name_short = filename[:32]
    print(
        f"{name_short:<34} | {t_text:.3f}s | {t_tables:.3f}s | {t_parse:.3f}s | {total:.3f}s | {status}"
    )

    # Show why the LLM was needed (only works if you added llm_reasons)
    if status == "LLM USED" and parsed.get("llm_reasons"):
        print("     why LLM:", parsed["llm_reasons"])

    # Show warnings from the parser
    warnings = parsed.get("validation_warnings") or []
    for w in warnings:
        print("     warning:", w)

    # Accuracy check
    if filename in expected:
        wrong = []
        for field in check_fields:
            if field not in expected[filename]:
                continue
            fields_checked += 1
            if same_value(field, parsed.get(field), expected[filename][field]):
                fields_right += 1
            else:
                wrong.append(field)
        if wrong:
            print("     WRONG fields:", wrong)

print("-" * 95)
print(f"TOTAL FILES:   {len(files)}")
print(f"REGEX ONLY:    {regex_count}")
print(f"LLM USED:      {llm_count}")
print(f"TOTAL TIME:    {total_time:.2f} seconds")

if regex_times:
    print(f"AVG (regex only): {sum(regex_times) / len(regex_times):.2f}s per file")
if llm_times:
    print(f"AVG (LLM used):   {sum(llm_times) / len(llm_times):.2f}s per file")

if fields_checked:
    print(f"FIELDS CORRECT: {fields_right} of {fields_checked}")
