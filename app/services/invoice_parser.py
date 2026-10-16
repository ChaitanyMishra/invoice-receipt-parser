import re

from app.services.llm_extractor import extract_missing_data_gemini, extract_missing_data_groq
from app.services.llm_extractor import extract_line_items_gemini , extract_line_items_groq
from crud_invoice import parse_date


def validate_field(field:str,value:str):
    if not value:
        return False
    if field == 'total' or field == 'tax_amount' or field == 'subtotal':
        try:
            float(value.replace(',', ''))
            return True
        except ValueError:
            return False

    if field == 'date':
        try:
            parse_date(value)
            return True
        except ValueError:
            return False

    if field == 'gstin':
        return bool(re.match(r"^\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]$", value))
    if field == 'invoice_number':
        bad = {"dated", "no", "bill", "invoice", "number"}
        return value.lower() not in bad
    return True

def cross_validation(parsed:dict):
    total = float(parsed.get('total' , '0').replace(',' , '')) if parsed.get('total') else None
    tax = float(parsed.get('tax_amount' , '0').replace(',','')) if parsed.get('tax_amount') else None
    # subtotal = float(parsed.get('subtotal', '0').replace(',','')) if parsed.get('subtotal') else None

    if total and tax and tax > total:
        # parsed['total'] = None
        parsed['tax_amount'] = None

    return parsed


FIELD_PATTERNS = {
"invoice_number": [
    r"Invoice Number\s*:\s*(\S+)",                      # Amazon
    r"Invoice No\.?\s*Dated\s*[\r\n]+\s*(\S+)",         # Supercloud (with "Dated" label)
    r"Invoice No\.?\s*[\r\n]+\s*([\w/]+-\d+)",          # Supercloud (no "Dated")
    r"Bill No\.?\s*:?\s*(\S+)",                         # Bill format
],
        "date": [
            r"Invoice Date\s*:\s*(\d{2}[./-]\d{2}[./-]\d{4})",
            r"Dated\s*:?\s*(\d{2}-[A-Za-z]{3}-\d{2,4})",
            r"Date\s*:\s*(\d{2}[./-]\d{2}[./-]\d{4})",
        ],
        "gstin": [
            r"GST Registration No\s*:\s*(\S+)",
            r"GSTIN/UIN\s*:\s*([\dA-Z]+)",
            r"GSTIN\s*:\s*([\dA-Z]+)",
        ],
        "order_number": [
            r"Order Number\s*:\s*(\S+)",
            r"Reference No\.?\s*&?\s*Date\.?\s*:?\s*(\S+/[\d/-]+)",
        ],
        "total": [
            r"TOTAL\s*:\s*₹\s*[\S.,]+\s*₹\s*([\S.,]+)",
            r"Total\s*\(cid:\d+\)\s*([\d,]+\.\d{2})",
            r"Total\s*:?\s*₹?\s*([\d,]+\.\d{2})",
            r"Grand Total\s*:?\s*₹?\s*([\d,]+(?:\.\d{1,2})?)"
        ],
        "tax_amount": [
            r"TOTAL\s*:\s*₹\s*([\S.,]+)\s*₹",
            r"IGST\s+([\d,]+\.\d{2})",
            r"Tax Amount\s*:?\s*([\d,]+\.\d{2})",
        ],
    }
def extract_field(field:str , text:str):
    # values = []
    for pattern in FIELD_PATTERNS[field]:
        match = re.search(pattern , text ,re.IGNORECASE)
        if match:
            try:
                # cap = match.group(1)
                # values.append(cap)
                return match.group(1)
            except IndexError:
                continue
    # if not values:
    #     return None
    # if len(set(values)) == 1:
    #     return values[0]
    # return None



def parse_invoice_text(text: str) -> dict:
    if not text:
        return {}
    parsed_text = {}
    vendor_name = re.search(r"(?m)^For\s+(.+?)\s*:\s*$", text)
    for field in FIELD_PATTERNS:
        parsed_text[field] = extract_field(field,text)

    for field in parsed_text:
        validate_field(field , parsed_text[field])
    cross_validation(parsed_text)
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
            print(f"Groq failed: {e}")
    if not llm_result:
        try:
            llm_result = extract_missing_data_gemini(text, missing_field)
        except Exception as e:
            print(f"Gemini failed: {e}")
    cross_validation(parsed_text)
    if isinstance(llm_result,dict):
        for field in missing_field:
            value = llm_result.get(field)
            if value:
                parsed_text[field] = value

    line_items = []
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
