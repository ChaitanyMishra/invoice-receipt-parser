import re

from app.services.llm_extractor import extract_missing_data_gemini, extract_missing_data_groq
from app.services.llm_extractor import extract_line_items_gemini , extract_line_items_groq


def parse_invoice_text(text: str) -> dict:
    if not text:
        return {}
    parsed_text = {}
    invoice_number = re.search(r"Invoice Number\s*:\s*(\S+)", text)
    invoice_date = re.search(r"Invoice Date\s*:\s*(\d{2}\.\d{2}\.\d{4})", text)
    gst_in = re.search(r"GST Registration No\s*:\s*(\S+)", text)
    order_number = re.search(r"Order Number\s*:\s*(\d{3}-\d{7}-\d{7})", text)
    total = re.search(r"TOTAL\s*:\s*₹\s*[\S.,]+\s*₹\s*([\S.,]+)", text)
    tax_amount = re.search(r"TOTAL\s*:\s*₹\s*([\S.,]+)\s*₹", text)
    vendor_name = re.search(r"(?m)^For\s+(.+?)\s*:\s*$", text)
    if invoice_number:
        parsed_text["invoice_number"] = invoice_number.group(1)
    else:
        parsed_text["invoice_number"] = None
    if invoice_date:
        parsed_text["date"] = invoice_date.group(1)
    else:
        parsed_text["date"] = None
    if gst_in:
        parsed_text["gstin"] = gst_in.group(1)
    else:
        parsed_text["gstin"] = None
    if order_number:
        parsed_text["order_number"] = order_number.group(1)
    else:
        parsed_text["order_number"] = None
    if total:
        parsed_text["total"] = total.group(1)
    else:
        parsed_text["total"] = None
    if tax_amount:
        parsed_text["tax_amount"] = tax_amount.group(1)
    else:
        parsed_text["tax_amount"] = None
    if vendor_name:
        parsed_text["vendor_name"] = vendor_name.group(1)
    else:
        parsed_text["vendor_name"] = None
    parsed_text["address"] = None
    missing_field = [key for key, value in parsed_text.items() if value is None]
    llm_result = {}
    if missing_field:
        try:
            llm_result = extract_missing_data_groq(text, missing_field)
        except Exception as e:
            # Log it, but don't crash
            print(f"LLM extraction failed: {e}")
        if not llm_result:
            try:
                llm_result = extract_missing_data_gemini(text, missing_field)
            except Exception as e:
                print(f"Groq failed: {e}")
    for field in missing_field:
        value = llm_result.get(field)
        if value:
            parsed_text[field] = llm_result[field]

    line_items = {}
    try:
        line_items = extract_line_items_groq(text)

    except Exception as e:
        print(f"LLM Extraction failed: {e}")

    if not line_items:
        try:
            line_items = extract_line_items_gemini(text)
        except Exception as e:
            print(f"LLM Extraction failed: {e}")
    parsed_text['line_items'] = line_items



    return parsed_text
