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


def test_extract_total_handles_ocr_prefix_and_ignores_tax_summary_row():
    text = """\
Taxable Value: 523,758.00
IGST 18%: 94,276.44
Total ī6,18,034.00
Total: 523,758.00 94,276.44 94,276.44
"""
    assert extract_total(text) == "618034.00"
    assert extract_tax(text) == "94276.44"


def test_extract_total_ignores_pdf_font_markers_in_tally_style_rows():
    text = """\
Total (cid:299) 6,18,034.00
Taxable IGST Total
Total: 5,23,758.00 94,276.44 94,276.44
"""
    assert extract_total(text) == "618034.00"


def test_extract_total_supports_common_accounting_labels():
    for label in (
        "Grand Total (including tax): ₹ 1,180.00",
        "Total Payable: INR 1,180.00",
        "Invoice Value: Rs. 1,180.00",
        "Amount Due: 1,180.00",
    ):
        assert extract_total(label) == "1180.00"


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


@patch(
    "app.services.invoice_parser.extract_invoice_data_gemini",
    return_value={"fields": {}, "line_items": []},
)
@patch(
    "app.services.invoice_parser.extract_invoice_data_groq",
    return_value={"fields": {}, "line_items": []},
)
def test_parser_keeps_total_and_subtotal_and_returns_review_warnings(
    groq_mock, gemini_mock
):
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
    groq_mock.assert_called_once()
    gemini_mock.assert_not_called()
