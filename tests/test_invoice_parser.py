import sys
import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.database import get_database_url
from app.main import app
from app.services.invoice_parser import (
    cross_validation,
    extract_tax,
    extract_total,
    gstin_checksum_ok,
    parse_amount,
    parse_invoice_text,
    should_run_deep_parse,
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


def test_gstin_checksum_validation_works_for_known_valid_and_invalid_values():
    assert gstin_checksum_ok("27ABCDE1234F1Z0") is True
    assert gstin_checksum_ok("27ABCDE1234F1Z9") is False


def test_deep_parse_policy_is_explicit_and_conservative():
    parsed = {
        "invoice_number": None,
        "date": None,
        "gstin": None,
        "vendor_name": None,
        "total": "1180.00",
    }

    assert should_run_deep_parse(parsed) is False
    assert should_run_deep_parse(parsed, force_llm=True) is True


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

    parsed = parse_invoice_text(text, force_llm=True)

    assert parsed["subtotal"] == "1000.00"
    assert parsed["tax_amount"] == "180.00"
    assert parsed["total"] == "1180.00"
    assert parsed["validation_warnings"] == [
        "Critical field missing: gstin.",
        "Critical field missing: vendor_name.",
        "No line items extracted.",
    ]
    groq_mock.assert_called_once()
    gemini_mock.assert_not_called()


@patch(
    "app.services.invoice_parser.extract_invoice_data_gemini",
    return_value={"fields": {}, "line_items": []},
)
@patch(
    "app.services.invoice_parser.extract_invoice_data_groq",
    return_value={"fields": {}, "line_items": []},
)
def test_parser_does_not_call_llm_without_force_llm(groq_mock, gemini_mock):
    parsed = parse_invoice_text(
        "Grand Total: 118.00\nTax Amount: 18.00\nTaxable Value: 100.00",
        fetch_optional=True,
    )

    assert parsed["total"] == "118.00"
    groq_mock.assert_not_called()
    gemini_mock.assert_not_called()


def test_database_url_rejects_sqlite_without_test_context(monkeypatch):
    monkeypatch.delenv("DB_URL", raising=False)
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(sys, "argv", ["uvicorn", "app.main:app"])

    with pytest.raises(RuntimeError, match="DB_URL must be set"):
        get_database_url()


def test_batch_upload_submits_each_file_to_celery():
    client = TestClient(app)
    email = f"batchqueueuser-{uuid.uuid4().hex[:8]}@example.com"

    response = client.post("/register", json={"email": email, "password": "Password123!"})
    assert response.status_code == 201

    login = client.post(
        "/login",
        data={"username": email, "password": "Password123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.main.celery_app.send_task") as send_task_mock:
        send_task_mock.side_effect = [type("Task", (), {"id": "task-1"})(), type("Task", (), {"id": "task-2"})()]
        response = client.post(
            "/batch-upload",
            files=[
                ("files", ("one.pdf", b"%PDF-1.4\ntext", "application/pdf")),
                ("files", ("two.pdf", b"%PDF-1.4\ntext", "application/pdf")),
            ],
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "processing"
    assert len(payload["task_ids"]) == 2
    assert send_task_mock.call_count == 2


def test_user_cannot_access_another_users_file():
    client = TestClient(app)
    user_a = f"usera-{uuid.uuid4().hex[:8]}@example.com"
    user_b = f"userb-{uuid.uuid4().hex[:8]}@example.com"

    client.post("/register", json={"email": user_a, "password": "Password123!"})
    client.post("/register", json={"email": user_b, "password": "Password123!"})

    token_a = client.post(
        "/login",
        data={"username": user_a, "password": "Password123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    ).json()["access_token"]
    token_b = client.post(
        "/login",
        data={"username": user_b, "password": "Password123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    ).json()["access_token"]

    upload = client.post(
        "/files",
        files=[("file", ("invoice.pdf", b"%PDF-1.4\ntext", "application/pdf"))],
        headers={"Authorization": f"Bearer {token_a}"},
    )
    file_id = upload.json()["id"]

    response = client.get(
        f"/files/{file_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 403
