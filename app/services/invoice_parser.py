import re
from decimal import Decimal, InvalidOperation

from app.services.llm_extractor import (
    extract_invoice_data_gemini,
    extract_invoice_data_groq,
)
from crud_invoice import parse_date

MONEY_FIELDS = {"total", "tax_amount", "subtotal"}
AMOUNT_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_/,])(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?(?!\d)"
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
            re.fullmatch(
                r"\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]", str(value).upper()
            )
        )
    if field == "invoice_number":
        bad = {"dated", "no", "bill", "invoice", "number"}
        return str(value).strip().lower() not in bad
    return True


def _line_amounts(line: str):
    line = re.sub(r"\(\s*cid\s*:\s*\d+\s*\)", " ", line, flags=re.IGNORECASE)
    return [parse_amount(value) for value in AMOUNT_TOKEN.findall(line)]


def extract_total(text: str):
    candidates = []
    lines = text.splitlines()
    excluded = re.compile(
        r"\b(?:sub[\s-]?total|taxable|cgst|sgst|igst|quantity|qty)\b", re.IGNORECASE
    )
    tax_total = re.compile(
        r"\b(?:total\s+(?:tax|gst|vat)|(?:tax|gst|vat)\s+total)\b", re.IGNORECASE
    )
    labels = (
        (
            5,
            re.compile(
                r"\b(?:grand\s+total|total\s+invoice\s+value|total\s+payable|net\s+payable)\b",
                re.IGNORECASE,
            ),
        ),
        (
            4,
            re.compile(
                r"\b(?:invoice\s+total|total\s+amount|invoice\s+amount|total\s+due|amount\s+due|amount\s+payable|invoice\s+value)\b",
                re.IGNORECASE,
            ),
        ),
        (2, re.compile(r"\btotal\b", re.IGNORECASE)),
    )

    for index, line in enumerate(lines):
        if excluded.search(line) or tax_total.search(line):
            continue
        strength = next(
            (rank for rank, pattern in labels if pattern.search(line)), None
        )
        if strength is None:
            continue
        values = _line_amounts(line)
        if (
            re.match(r"\s*total\s*:", line, re.IGNORECASE)
            and len([value for value in values if value is not None]) > 1
        ):
            continue
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
        if re.search(r"\btaxable\b", line, re.IGNORECASE):
            continue
        values = [value for value in _line_amounts(line) if value is not None]
        if not values:
            continue
        if re.search(r"\b(?:total\s+tax|tax\s+amount)\b", line, re.IGNORECASE):
            explicit.append(values[-1])
        elif re.search(r"\btotal\b", line, re.IGNORECASE) and len(values) >= 2:
            explicit.append(values[-2])
        elif re.search(r"\b(?:cgst|sgst|igst|vat)\b", line, re.IGNORECASE):
            components.append(values[-1])

    tax = (
        explicit[-1]
        if explicit
        else sum(components, Decimal(0))
        if components
        else None
    )
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
            Decimal(0),
        )
        if item_total and abs(item_total - subtotal) > Decimal("1.00"):
            warnings.append("Line-item amounts do not match the taxable subtotal.")
    parsed["validation_warnings"] = warnings
    return parsed


FIELD_PATTERNS = {
    "invoice_number": [
        r"Invoice Number\s*:\s*(\S+)",
        r"Invoice No\.?\s*Dated\s*[\r\n]+\s*(\S+)",
        r"Invoice No\.?\s*[\r\n]+\s*([\w/]+-\d+)",
        r"Bill No\.?\s*:?\s*(\S+)",
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


def extract_field(field: str, text: str):
    for pattern in FIELD_PATTERNS[field]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def parse_invoice_text(text: str, use_llm: bool = True) -> dict:
    if not text:
        return {}
    parsed_text = {}
    vendor_name = re.search(r"(?m)^For\s+(.+?)\s*:\s*$", text)
    for field in FIELD_PATTERNS:
        parsed_text[field] = (
            extract_total(text)
            if field == "total"
            else extract_tax(text)
            if field == "tax_amount"
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
        key
        for key, value in parsed_text.items()
        if value is None and key not in MONEY_FIELDS
    ]
    llm_result = {}
    if use_llm:
        try:
            llm_result = extract_invoice_data_groq(text, missing_field)
        except Exception as e:
            print(f"Groq failed: {e}")
    if use_llm and not llm_result:
        try:
            llm_result = extract_invoice_data_gemini(text, missing_field)
        except Exception as e:
            print(f"Gemini failed: {e}")

    llm_fields = llm_result.get("fields", llm_result)
    if isinstance(llm_fields, dict):
        for field in missing_field:
            value = llm_fields.get(field)
            if value is not None and validate_field(field, value):
                parsed_text[field] = str(value)
            elif value is not None:
                parsed_text[field] = None

    line_items = llm_result.get("line_items", []) if use_llm else []
    if not isinstance(line_items, list):
        line_items = []

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
