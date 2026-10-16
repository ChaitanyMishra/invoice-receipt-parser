import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from openai import OpenAI

load_dotenv()


def extract_missing_data_gemini(text: str, missing_data: list) -> dict:
    if not text:
        return {}
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    field_list = ", ".join(missing_data)
    prompt = f'''You are an invoice parser. Extract ONLY these fields: {field_list}

    Important definitions (apply only to fields in the list above):
    - vendor_name: the name of the SELLER (company that issued the invoice), NOT the buyer
    - address: the SELLER's address only (the vendor's address, NOT the buyer's or shipping address)
    - invoice_number: the invoice identifier (e.g., "1/Bihar/25-26", "POD-26-241475108")
    - date: the invoice date (return as shown in the invoice)
    - gstin: the seller's GST registration number (15 characters, e.g., "10AAYCS0991B1ZD")
    - order_number: the order reference (e.g., "Bihar/PMF/0001")
    - total: the GRAND TOTAL after taxes and round-offs. This is the LARGEST number
    on the invoice. It MUST be greater than tax_amount.
    - tax_amount: the TOTAL TAX (CGST + SGST + IGST combined). This MUST be LESS
    than total. If your answer is greater than total, you made an arithmetic error.
    - subtotal: the TAXABLE value (amount BEFORE tax). Often labeled "Taxable Value"
    or "Sub Total".

    Rules:
    - Return numbers only for numeric fields. Strip currency symbols (₹, Rs, $) and commas.
    - Return dates in YYYY-MM-DD format.
    - If a field is not found, use null. Do NOT invent values.
    - Do NOT include fields that are not in the list above.

    Return a single JSON object with exactly these keys: {field_list}

    Invoice text:
    {text}'''

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return json.loads(response.text) if response.text else {}


def extract_missing_data_groq(text: str, missing_data: list) -> dict:
    if not text:
        return {}
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1", api_key=os.getenv("GROQ_API_KEY")
    )

    field_list = ", ".join(missing_data)
    prompt = f'''You are an invoice parser. Extract ONLY these fields: {field_list}

    Important definitions (apply only to fields in the list above):
    - vendor_name: the name of the SELLER (company that issued the invoice), NOT the buyer
    - address: the SELLER's address only (the vendor's address, NOT the buyer's or shipping address)
    - invoice_number: the invoice identifier (e.g., "1/Bihar/25-26", "POD-26-241475108")
    - date: the invoice date (return as shown in the invoice)
    - gstin: the seller's GST registration number (15 characters, e.g., "10AAYCS0991B1ZD")
    - order_number: the order reference (e.g., "Bihar/PMF/0001")
    - total: the GRAND TOTAL after taxes and round-offs. This is the LARGEST number
    on the invoice. It MUST be greater than tax_amount.
    - tax_amount: the TOTAL TAX (CGST + SGST + IGST combined). This MUST be LESS
    than total. If your answer is greater than total, you made an arithmetic error.
    - subtotal: the TAXABLE value (amount BEFORE tax). Often labeled "Taxable Value"
    or "Sub Total".

    Rules:
    - Return numbers only for numeric fields. Strip currency symbols (₹, Rs, $) and commas.
    - Return dates in YYYY-MM-DD format.
    - If a field is not found, use null. Do NOT invent values.
    - Do NOT include fields that are not in the list above.

    Return a single JSON object with exactly these keys: {field_list}

    Invoice text:
    {text}'''
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return (
        json.loads(response.choices[0].message.content)
        if response.choices[0].message.content
        else {}
    )
# LineItems Extraction

def extract_line_items_gemini(text:str) -> list:
    client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
    prompt = f'''You are an invoice parser. Extract all line items from this invoice text.

    Return a JSON object with a single key "line_items" containing an array.

    Each item in the array should have:
    - description: the full item description (text from the "Particulars", "Description", or "Item" column)
    - quantity: the quantity (number, or null if not shown)
    - unit_price: the price per unit (number, no currency symbols, or null if not shown)
    - amount: the TAXABLE value of the line item (the amount BEFORE tax, not the grand total)

    Rules:
    - Only include rows from the itemized table (the "Particulars", "Description", or "Item" column).
    - Do NOT include:
    - round-off lines
    - subtotal or total lines
    - tax lines (CGST, SGST, IGST, VAT)
    - "Amount in Words" sections
    - signature blocks ("Authorised Signatory", "For X Pvt Ltd")
    - terms and conditions
    - headers (Sl No, Description, Qty, Rate, Amount)
    - Most invoices have 1-3 line items. If you return more than 5, you are including non-item text. Remove those.
    - Return numbers only, never strings. Strip currency symbols (₹, Rs, $).
    - Do NOT include trailing colons or extra punctuation in the description.

    If no line items are found, return {{"line_items": []}}.

    Example:
    {{
    "line_items": [
        {{"description": "Portfolio Management Fee", "quantity": null, "unit_price": null, "amount": 3546894.00}},
        {{"description": "Shipping Charges", "quantity": 1, "unit_price": 66.94, "amount": 66.94}}
    ]
    }}

    Invoice text:
    {text}'''
    response = client.models.generate_content(
        model='gemini-3.5-flash-lite',
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type='application/json')
    )
    content = response.text
    if not content:
        return []
    parsed = json.loads(content)
    return parsed.get('line_items',[])

def extract_line_items_groq(text:str) -> list:
    if not text:
        return []
    client = OpenAI(base_url="https://api.groq.com/openai/v1",api_key=os.getenv('GROQ_API_KEY'))
    prompt = f'''You are an invoice parser. Extract all line items from this invoice text.

    Return a JSON object with a single key "line_items" containing an array.

    Each item in the array should have:
    - description: the full item description (text from the "Particulars", "Description", or "Item" column)
    - quantity: the quantity (number, or null if not shown)
    - unit_price: the price per unit (number, no currency symbols, or null if not shown)
    - amount: the TAXABLE value of the line item (the amount BEFORE tax, not the grand total)

    Rules:
    - Only include rows from the itemized table (the "Particulars", "Description", or "Item" column).
    - Do NOT include:
    - round-off lines
    - subtotal or total lines
    - tax lines (CGST, SGST, IGST, VAT)
    - "Amount in Words" sections
    - signature blocks ("Authorised Signatory", "For X Pvt Ltd")
    - terms and conditions
    - headers (Sl No, Description, Qty, Rate, Amount)
    - Most invoices have 1-3 line items. If you return more than 5, you are including non-item text. Remove those.
    - Return numbers only, never strings. Strip currency symbols (₹, Rs, $).
    - Do NOT include trailing colons or extra punctuation in the description.

    If no line items are found, return {{"line_items": []}}.

    Example:
    {{
    "line_items": [
        {{"description": "Portfolio Management Fee", "quantity": null, "unit_price": null, "amount": 3546894.00}},
        {{"description": "Shipping Charges", "quantity": 1, "unit_price": 66.94, "amount": 66.94}}
    ]
    }}

    Invoice text:
    {text}'''
    response = client.chat.completions.create(
    model="openai/gpt-oss-20b",
    messages=[{'role':'user','content':prompt}],
    response_format={"type":'json_object'}
    )
    raw = response.choices[0].message.content
    if not raw:
        return []
    return json.loads(raw).get("line_items", [])


