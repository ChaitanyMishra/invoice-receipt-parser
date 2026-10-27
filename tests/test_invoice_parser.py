from decimal import Decimal
from unittest.mock import patch

from app.services.invoice_parser import (
    cross_validation,
    extract_tax,
    extract_total,
    parse_amount,
    parse_invoice_text,
)


def test_parse_amount_accepts_indian_grouping_and_rejects_malformed_values():
    assert parse_amount("₹ 1,23,456.78") == Decimal("123456.78")
    assert parse_amount("1,234.50") == Decimal("1234.50")
    assert parse_amount("1,2,34.50") is None


def test_extract_total_uses_payable_line_instead_of_tax_or_subtotal():
    text = """\
Taxable Value: ₹ 1,000.00
CGST 9%: ₹ 90.00
SGST 9%: ₹ 90.00
Grand Total: ₹ 1,180.00
"""
    assert extract_total(text) == "1180.00"
    assert extract_tax(text) == "180.00"


def test_cross_validation_flags_inconsistent_invoice_arithmetic():
    parsed = {
        "subtotal": "1000.00",
        "tax_amount": "180.00",
        "total": "100.00",
        "line_items": [],
    }

    cross_validation(parsed)

    assert (
        "Invoice total is less than the taxable subtotal."
        in parsed["validation_warnings"]
    )


@patch("app.services.invoice_parser.extract_line_items_gemini", return_value=[])
@patch("app.services.invoice_parser.extract_line_items_groq", return_value=[])
@patch("app.services.invoice_parser.extract_missing_data_gemini", return_value={})
@patch("app.services.invoice_parser.extract_missing_data_groq", return_value={})
def test_parser_keeps_total_and_subtotal_and_returns_review_warnings(*_mocks):
    text = """\
Invoice Number: INV-42
Invoice Date: 01-10-2026
Taxable Value: ₹ 1,000.00
CGST 9%: ₹ 90.00
SGST 9%: ₹ 90.00
Grand Total: ₹ 1,180.00
"""

    parsed = parse_invoice_text(text)

    assert parsed["subtotal"] == "1000.00"
    assert parsed["tax_amount"] == "180.00"
    assert parsed["total"] == "1180.00"
    assert parsed["validation_warnings"] == []
