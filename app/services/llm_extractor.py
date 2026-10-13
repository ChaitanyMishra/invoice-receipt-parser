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
    prompt = f"""
You are an invoice parser. Extract ONLY these fields: {field_list}

Important definitions (apply only to fields in the list above):
- vendor_name: the name of the SELLER (company that issued the invoice), NOT the buyer
- address: the SELLER's address only, NOT the buyer's or shipping address
- invoice_number: the invoice identifier
- date: the invoice date
- gstin: the seller's GST number
- order_number: the order reference
- total: the grand total
- tax_amount: the total tax

Return a single JSON object with exactly these keys: {field_list}
If a field is not found, use null.
DO NOT include fields that are not in the list above.

Invoice text:
{text}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
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
    prompt = f"""
You are an invoice parser. Extract ONLY these fields: {field_list}

Important definitions (apply only to fields in the list above):
- vendor_name: the name of the SELLER (company that issued the invoice), NOT the buyer
- address: the SELLER's address only, NOT the buyer's or shipping address
- invoice_number: the invoice identifier
- date: the invoice date
- gstin: the seller's GST number
- order_number: the order reference
- total: the grand total
- tax_amount: the total tax

Return a single JSON object with exactly these keys: {field_list}
If a field is not found, use null.
DO NOT include fields that are not in the list above.

Invoice text:
{text}
"""
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
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
- description: the full item description (the text in the "Description" or "Item" column)
- quantity: the quantity (number, or null if not shown)
- unit_price: the price per unit (number, no currency symbols, or null if not shown)
- amount: the final line total after tax (number, no currency symbols)

Rules:
- Do NOT include trailing colons or punctuation in the description.
- If quantity is shown, unit_price × quantity may not equal amount — amount includes tax.
- Return numbers only, never strings.

If no line items are found, return {{"line_items": []}}.

Example:
{{
"line_items": [
    {{"description": "Boat Earphones", "quantity": 1, "unit_price": 295.76, "amount": 349.00}},
    {{"description": "Shipping Charges", "quantity": 1, "unit_price": 66.94, "amount": 79.00}}
]
}}

Invoice text:
{text}'''
    response = client.models.generate_content(
        model='gemini-2.5-flash',
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
- description: the full item description (the text in the "Description" or "Item" column)
- quantity: the quantity (number, or null if not shown)
- unit_price: the price per unit (number, no currency symbols, or null if not shown)
- amount: the final line total after tax (number, no currency symbols)

Rules:
- Do NOT include trailing colons or punctuation in the description.
- If quantity is shown, unit_price × quantity may not equal amount — amount includes tax.
- Return numbers only, never strings.

If no line items are found, return {{"line_items": []}}.

Example:
{{
"line_items": [
    {{"description": "Boat Earphones", "quantity": 1, "unit_price": 295.76, "amount": 349.00}},
    {{"description": "Shipping Charges", "quantity": 1, "unit_price": 66.94, "amount": 79.00}}
]
}}

Invoice text:
{text}'''
    response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[{'role':'user','content':prompt}],
    response_format={"type":'json_object'}
    )
    raw = response.choices[0].message.content
    if not raw:
        return []
    return json.loads(raw).get("line_items", [])

