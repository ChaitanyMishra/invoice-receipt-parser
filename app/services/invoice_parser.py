from decimal import Decimal, InvalidOperation
import re

from app.services.llm_extractor import extract_missing_data_gemini, extract_missing_data_groq
from app.services.llm_extractor import extract_line_items_gemini , extract_line_items_groq
from crud_invoice import parse_date


MONEY_FIELDS = {"total", "tax_amount", "subtotal"}
AMOUNT_TOKEN = re.compile(
    r"(?<![\w/])(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?(?!\d)"
)


def parse_amount(value):
    if value is None:
        return None
    cleaned = re.sub(
        r"^(?:₹|INR|Rs\.?)\s*", "", str(value).strip(), flags=re.IGNORECASE
    )
    cleaned = cleaned.strip()
    valid_number = (
        r"(?:\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3}|\d+)"
        r"(?:\.\d{1,2})?"
    )
    if not re.fullmatch(valid_number, cleaned):
        return None
    cleaned = cleaned.replace(",", "")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        return None
    return amount if amount >= 0 else None


def parse_quantity(value):
    if value is None or value == "":
        return None
    try:
        quantity = Decimal(str(value).strip().replace(",", ""))
    except InvalidOperation:
        return None
    return quantity if quantity.is_finite() and quantity >= 0 else None


def validate_field(field: str, value):
    if value is None or value == "":
        return False
    if field in MONEY_FIELDS:
        return parse_amount(value) is not None
    if field == "date":
        try:
            parse_date(str(value))
            return True
        except ValueError:
            return False
    if field == "gstin":
        return bool(
            re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]", str(value).upper())
        )
    if field == "invoice_number":
        bad = {"dated", "no", "bill", "invoice", "number"}
        return str(value).strip().lower() not in bad
    return True


def _line_amounts(line: str):
    return [parse_amount(value) for value in AMOUNT_TOKEN.findall(line)]


def extract_total(text: str):
    candidates = []
    lines = text.splitlines()
    excluded = re.compile(r"\b(?:sub[\s-]?total|taxable|cgst|sgst|igst|tax|quantity|qty)\b", re.I)
    labels = (
        (5, re.compile(r"\b(?:grand\s+total|net\s+payable|amount\s+payable)\b", re.I)),
        (4, re.compile(r"\b(?:invoice\s+total|total\s+amount)\b", re.I)),
        (2, re.compile(r"\btotal\b", re.I)),
    )

    for index, line in enumerate(lines):
        if excluded.search(line):
            continue
        strength = next((rank for rank, pattern in labels if pattern.search(line)), None)
        if strength is None:
            continue
        values = _line_amounts(line)
        if not values and index + 1 < len(lines):
            values = _line_amounts(lines[index + 1])
        values = [value for value in values if value is not None]
        if values:
            candidates.append((strength, index, values[-1]))

    if not candidates:
        return None
    return str(max(candidates, key=lambda item: (item[0], item[1]))[2])


def extract_tax(text: str):
    explicit = []
    components = []
    for line in text.splitlines():
        if re.search(r"\btaxable\b", line, re.I):
            continue
        values = [value for value in _line_amounts(line) if value is not None]
        if not values:
            continue
        if re.search(r"\b(?:total\s+tax|tax\s+amount)\b", line, re.I):
            explicit.append(values[-1])
        elif re.search(r"\btotal\b", line, re.I) and len(values) >= 2:
            explicit.append(values[-2])
        elif re.search(r"\b(?:cgst|sgst|igst|vat)\b", line, re.I):
            components.append(values[-1])

    tax = explicit[-1] if explicit else sum(components, Decimal("0")) if components else None
    return str(tax) if tax is not None else None


def cross_validation(parsed: dict):
    warnings = []
    values = {}
    for field in MONEY_FIELDS:
        amount = parse_amount(parsed.get(field))
        if parsed.get(field) not in (None, "") and amount is None:
            warnings.append(f"{field.replace('_', ' ').title()} is not a valid amount.")
            parsed[field] = None
        elif amount is not None:
            parsed[field] = format(amount, "f")
        values[field] = amount

    total = values["total"]
    subtotal = values["subtotal"]
    tax = values["tax_amount"]
    if total is None:
        warnings.append("Total could not be verified from the invoice text.")
    if total is not None and tax is not None and tax > total:
        warnings.append("Tax is greater than the invoice total.")
    if total is not None and subtotal is not None and total < subtotal:
        warnings.append("Invoice total is less than the taxable subtotal.")
    if total is not None and subtotal is not None and tax is not None:
        if abs(total - subtotal - tax) > Decimal("1.00"):
            warnings.append("Subtotal plus tax does not match the invoice total.")

    line_items = parsed.get("line_items", [])
    for item in line_items:
        quantity = item.get("quantity")
        unit_price = parse_amount(item.get("unit_price"))
        item_amount = parse_amount(item.get("amount"))
        quantity_value = parse_quantity(quantity)
        if (
            quantity_value is not None
            and unit_price is not None
            and item_amount is not None
            and abs(quantity_value * unit_price - item_amount) > Decimal("1.00")
        ):
            warnings.append(
                "A line-item amount does not match its quantity and unit price."
            )
            break

    if line_items and subtotal is not None:
        item_total = sum(
            (
                parse_amount(item.get("amount"))
                for item in line_items
                if parse_amount(item.get("amount")) is not None
            ),
            Decimal("0"),
        )
        if item_total and abs(item_total - subtotal) > Decimal("1.00"):
            warnings.append("Line-item amounts do not match the taxable subtotal.")
    parsed["validation_warnings"] = warnings
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
            r"Grand Total\s*:?\s*₹?\s*([\d,]+(?:\.\d{1,2})?)",
        ],
        "tax_amount": [
            r"Tax Amount\s*:?\s*₹?\s*([\d,]+(?:\.\d{1,2})?)",
        ],
        "subtotal": [
            r"(?:Taxable Value|Sub[\s-]?Total)\s*:?\s*₹?\s*([\d,]+(?:\.\d{1,2})?)",
        ],
    }
def extract_field(field:str , text:str):
    for pattern in FIELD_PATTERNS[field]:
        match = re.search(pattern , text ,re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def parse_invoice_text(text: str) -> dict:
    if not text:
        return {}
    parsed_text = {}
    vendor_name = re.search(r"(?m)^For\s+(.+?)\s*:\s*$", text)
    for field in FIELD_PATTERNS:
        parsed_text[field] = (
            extract_total(text) if field == "total"
            else extract_tax(text) if field == "tax_amount"
            else extract_field(field, text)
        )
        if parsed_text[field] is not None and not validate_field(
            field, parsed_text[field]
        ):
            parsed_text[field] = None

    if vendor_name:
        parsed_text["vendor_name"] = vendor_name.group(1)
    else:
        parsed_text["vendor_name"] = None
    parsed_text["address"] = None

    missing_field = [
        key for key, value in parsed_text.items() if value is None
    ]
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
    if isinstance(llm_result,dict):
        for field in missing_field:
            value = llm_result.get(field)
            if value is not None and validate_field(field, value):
                parsed_text[field] = str(value)
            elif value is not None:
                parsed_text[field] = None

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
    parsed_text["line_items"] = [
        {
            "description": str(item["description"]).strip(),
            "amount": str(parse_amount(item.get("amount"))),
            "unit_price": (
                str(parse_amount(item.get("unit_price")))
                if parse_amount(item.get("unit_price")) is not None
                else None
            ),
            "quantity": (
                str(parse_quantity(item.get("quantity")))
                if parse_quantity(item.get("quantity")) is not None
                else None
            ),
        }
        for item in line_items
        if isinstance(item, dict)
        and item.get("description")
        and parse_amount(item.get("amount")) is not None
    ]

    return cross_validation(parsed_text)
