import re
from decimal import Decimal, InvalidOperation

from app.services.llm_extractor import (
    extract_invoice_data_gemini,
    extract_invoice_data_groq,
)
from crud_invoice import parse_date

MONEY_FIELDS = {"total", "tax_amount", "subtotal"}
CRITICAL_FIELDS = ("invoice_number", "date", "total", "gstin", "vendor_name")

OPTIONAL_FIELDS = ("order_number", "address")

STRICT_GSTIN_CHECKSUM = False

AMOUNT_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_/,])(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?(?!\d)"
)

GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_PATTERN = r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]"
GSTIN_FULL = re.compile(GSTIN_PATTERN)
GSTIN_SEARCH = re.compile(r"(?<![0-9A-Z])" + GSTIN_PATTERN + r"(?![0-9A-Z])")


def gstin_checksum_ok(gstin: str) -> bool:
    """15th character of a GSTIN is a check digit (mod-36) of the first 14."""
    gstin = str(gstin).strip().upper()
    if not GSTIN_FULL.fullmatch(gstin):
        return False
    total = 0
    for index, char in enumerate(gstin[:14]):
        product = GSTIN_CHARS.index(char) * (1 if index % 2 == 0 else 2)
        total += product // 36 + product % 36
    return GSTIN_CHARS[(36 - total % 36) % 36] == gstin[14]


def _gstin_state_ok(gstin: str) -> bool:
    code = int(gstin[:2])
    return 1 <= code <= 38 or code in (97, 99)


def all_gstins(text: str):
    """Every distinct GSTIN-shaped token in the text, in order of appearance."""
    return list(dict.fromkeys(GSTIN_SEARCH.findall(text.upper())))


def extract_gstin(text: str):
    for pattern in FIELD_PATTERNS["gstin"]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and GSTIN_FULL.fullmatch(match.group(1).upper()):
            return match.group(1).upper()
    found = all_gstins(text)
    return found[0] if found else None

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
        gstin = str(value).strip().upper()
        if not GSTIN_FULL.fullmatch(gstin) or not _gstin_state_ok(gstin):
            return False
        if STRICT_GSTIN_CHECKSUM and not gstin_checksum_ok(gstin):
            return False
        return True
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


HEADER_ALIASES = {
    "description": ("description", "particulars", "item", "product", "goods"),
    "quantity": ("quantity", "qty"),
    "unit_price": ("unit price", "rate", "price"),
    "amount": ("amount", "taxable value", "total", "value"),
}
TAX_HEADER = re.compile(r"\b(?:gst|cgst|sgst|igst|tax)\b|%", re.IGNORECASE)
TOTAL_ROW = re.compile(r"\b(?:sub[\s-]?total|grand\s+total|total)\b", re.IGNORECASE)


def extract_tables_from_pdf(pdf_path):
    """Call this next to your existing text extraction and pass the result as
    `tables=` to parse_invoice_text."""
    import pdfplumber

    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables.extend(page.extract_tables())
    return tables


def _norm(cell):
    return re.sub(r"\s+", " ", str(cell or "")).strip().lower()


def _first_number(cell):
    match = re.search(r"\d[\d,]*(?:\.\d+)?", str(cell or ""))
    return match.group(0) if match else None


def _cell(row, index):
    if index is None or index >= len(row):
        return None
    return row[index]


def _map_columns(cells):
    mapping = {}
    for index, text in enumerate(cells):
        if not text:
            continue
        for field, aliases in HEADER_ALIASES.items():
            if field in mapping:
                continue
            if field in ("unit_price", "amount") and TAX_HEADER.search(text):
                continue
            if any(alias in text for alias in aliases):
                mapping[field] = index
                break
    return mapping


def _row_to_item(row, columns):
    description = re.sub(
        r"\s+", " ", str(_cell(row, columns.get("description")) or "")
    ).strip()
    if not description or TOTAL_ROW.search(description):
        return None
    amount = parse_amount(_first_number(_cell(row, columns.get("amount"))))
    if amount is None:
        return None
    quantity = parse_quantity(_first_number(_cell(row, columns.get("quantity"))))
    unit_price = parse_amount(_first_number(_cell(row, columns.get("unit_price"))))
    return {
        "description": description,
        "quantity": str(quantity) if quantity is not None else None,
        "unit_price": str(unit_price) if unit_price is not None else None,
        "amount": str(amount),
    }


def extract_line_items_from_tables(tables):
    items = []
    for table in tables or []:
        columns = None
        for row in table:
            cells = [_norm(cell) for cell in row]
            if columns is None:
                found = _map_columns(cells)
                if "description" in found and "amount" in found:
                    columns = found
                continue
            item = _row_to_item(row, columns)
            if item:
                items.append(item)
    return items


def line_items_verified(items, subtotal):
    """Only trust regex/table line items if the arithmetic proves them."""
    if not items:
        return False
    tolerance = Decimal("1.00")
    amounts = []
    fully_checkable = True
    for item in items:
        quantity = parse_quantity(item.get("quantity"))
        unit_price = parse_amount(item.get("unit_price"))
        amount = parse_amount(item.get("amount"))
        if amount is None:
            return False
        amounts.append(amount)
        if quantity is not None and unit_price is not None:
            if abs(quantity * unit_price - amount) > tolerance:
                return False
        else:
            fully_checkable = False
    if subtotal is not None:
        return abs(sum(amounts, Decimal(0)) - subtotal) <= tolerance
    return fully_checkable


def _normalise_items(raw_items):
    if not isinstance(raw_items, list):
        return []
    return [
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
        for item in raw_items
        if isinstance(item, dict)
        and item.get("description")
        and parse_amount(item.get("amount")) is not None
    ]

def cross_validation(parsed: dict, extra_warnings=None):
    warnings = list(extra_warnings or [])
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
        r"(?:Invoice\s*)?Date\s*:?\s*(\d{2}[./-]\d{2}[./-]\d{4})",
        r"Dated\s*:?\s*(\d{2}-[A-Za-z]{3}-\d{2,4})",
        r"Date\s*:\s*(\d{2}[./-]\d{2}[./-]\d{4})",
        r"(\d{2}-[A-Za-z]{3}-\d{2,4})",
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


def _grounded(value, text) -> bool:
    """An identifier from the LLM is only accepted if it literally appears in
    the document text. Stops the LLM from inventing a GSTIN or invoice number."""
    squeeze = lambda s: re.sub(r"\s+", "", str(s)).upper()
    return squeeze(value) in squeeze(text)

def parse_invoice_text(
    text: str,
    force_llm: bool = False, 
    tables=None,
    fetch_optional: bool = False,
) -> dict:
    if not text:
        return {}

    parsed_text = {}

    # 1. Extract standard fields
    for field in FIELD_PATTERNS:
        if field == "total":
            value = extract_total(text)
        elif field == "tax_amount":
            value = extract_tax(text)
        elif field == "gstin":
            value = extract_gstin(text)
        else:
            value = extract_field(field, text)
        if value is not None and not validate_field(field, value):
            value = None
        parsed_text[field] = value

    vendor_match = re.search(r"(?m)^(.+?)\s+Invoice No\.?\s*(?:Dated)?", text, re.IGNORECASE)

    # Fallback 1: Look for "for Vendor Name"
    if not vendor_match:
        vendor_match = re.search(r"(?mi)^for\s+(.+?)(?:\s*:\s*)?$", text)

    # Fallback 2: Grab the first line that doesn't contain standard header words
    if not vendor_match:
        lines = text.strip().splitlines()
        for line in lines[:5]:
            if not re.search(r"(?i)tax invoice|e-invoice|irn|ack no|ack date", line):
                vendor_match = re.match(r"^(.+?)(?:\s+202\d|\s+Invoice)", line)
                if vendor_match:
                    break

    parsed_text["vendor_name"] = vendor_match.group(1).strip() if vendor_match else None
    parsed_text["address"] = None

    # 3. Line Items
    line_items = extract_line_items_from_tables(tables) if tables else []
    if not line_items_verified(line_items, parse_amount(parsed_text.get("subtotal"))):
        line_items = []

    # 4. LLM Fallback
    wanted = [
        field
        for field in CRITICAL_FIELDS
        if field not in MONEY_FIELDS and parsed_text.get(field) is None
    ]
    if fetch_optional:
        wanted += [f for f in OPTIONAL_FIELDS if parsed_text.get(f) is None]

    need_llm = force_llm

    llm_used = False
    llm_result = {}
    if need_llm:
        llm_used = True
        try:
            llm_result = extract_invoice_data_groq(text, wanted)
        except Exception as e:
            print(f"Groq failed: {e}")
        if not llm_result:
            try:
                llm_result = extract_invoice_data_gemini(text, wanted)
            except Exception as e:
                print(f"Gemini failed: {e}")

    llm_fields = llm_result.get("fields", llm_result)
    if isinstance(llm_fields, dict):
        for field in wanted:
            value = llm_fields.get(field)
            if value is None:
                continue
            if not validate_field(field, value):
                continue
            if field in ("gstin", "invoice_number") and not _grounded(value, text):
                continue
            parsed_text[field] = (
                str(value).upper() if field == "gstin" else str(value)
            )

    if not line_items and need_llm:
        line_items = _normalise_items(llm_result.get("line_items", []))
    parsed_text["line_items"] = line_items

    # 5. Warnings
    extra = []
    for field in CRITICAL_FIELDS:
        if field not in MONEY_FIELDS and parsed_text.get(field) is None:
            extra.append(f"Critical field missing: {field}.")
    gstin = parsed_text.get("gstin")
    if gstin and not gstin_checksum_ok(gstin):
        extra.append("GSTIN check digit is invalid; verify the GSTIN manually.")
    found_gstins = all_gstins(text)
    if len(found_gstins) > 1:
        extra.append(
            f"{len(found_gstins)} different GSTINs found; the vendor GSTIN is "
            "assumed to be the first one. Verify."
        )
    if not line_items:
        extra.append("No line items extracted.")

    parsed_text["llm_used"] = llm_used
    return cross_validation(parsed_text, extra)
