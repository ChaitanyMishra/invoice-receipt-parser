from google import genai
import os
from dotenv import load_dotenv
from google.genai import types
from openai import OpenAI
import json

load_dotenv()



def extract_missing_data(text: str, missing_data: list) -> dict:
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
    return json.loads(response.choices[0].message.content) if response.choices[0].message.content else {}
