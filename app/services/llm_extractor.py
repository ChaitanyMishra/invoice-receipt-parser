import json
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types
from openai import OpenAI, RateLimitError

load_dotenv()

GROQ_MODEL = "openai/gpt-oss-20b"
GEMINI_MODEL = "gemini-3.5-flash-lite"

# We make the clients only once and reuse them.
# (Making a new client for every call wastes time.)
groq_client = None
gemini_client = None


def get_groq_client():
    global groq_client
    if groq_client is None:
        # max_retries=0 means the library will NOT secretly retry.
        # We handle the retry ourselves below so we can see what happens.
        groq_client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=os.getenv("GROQ_API_KEY"),
            timeout=15.0,
            max_retries=0,
        )
    return groq_client


def get_gemini_client():
    global gemini_client
    if gemini_client is None:
        gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return gemini_client


# What each field means. We only send the ones we actually need.
FIELD_HELP = {
    "vendor_name": "name of the SELLER (the company that made the invoice), not the buyer",
    "address": "address of the SELLER only, not the buyer or shipping address",
    "invoice_number": "the invoice number, copied exactly as written on the invoice",
    "date": "the invoice date in DD-MM-YYYY format",
    "gstin": "GSTIN of the SELLER, 15 characters, copied exactly as written",
    "order_number": "the order or reference number, only if it is shown",
}


def make_prompt(text, missing_fields):
    lines = []
    lines.append("Read the invoice text below and return ONE JSON object.")
    lines.append("")
    lines.append('The JSON must have two keys: "fields" and "line_items".')
    lines.append("")

    if missing_fields:
        lines.append('"fields" must contain only these keys:')
        for name in missing_fields:
            lines.append("- " + name + ": " + FIELD_HELP.get(name, ""))
    else:
        lines.append('"fields" must be an empty object.')

    lines.append("")
    lines.append('"line_items" is a list of the rows in the item table.')
    lines.append("Each row has: description, quantity, unit_price, amount.")
    lines.append("- amount is the value of that row BEFORE tax")
    lines.append("- use plain numbers (no currency symbols, no commas)")
    lines.append("- use null if a value is not shown")
    lines.append("- do NOT include: tax lines, subtotal, total, round-off,")
    lines.append("  table headers, amount in words, signature or terms text")
    lines.append("- if there are no item rows, return an empty list")
    lines.append("")
    lines.append("Do not guess. If a field is not found, use null.")
    lines.append("")
    lines.append("Invoice text:")
    lines.append(text)

    return "\n".join(lines)


def call_groq(prompt):
    client = get_groq_client()

    # Try at most 2 times. Only retry when Groq says "too many requests".
    for attempt in range(2):
        try:
            reply = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0,
                max_completion_tokens=2000,
                # "low" = the model thinks less, so it answers faster.
                # Invoice reading is easy, it does not need deep thinking.
                extra_body={"reasoning_effort": "low"},
            )
            return reply.choices[0].message.content
        except RateLimitError:
            if attempt == 1:
                raise  # second time also failed, let the caller use Gemini
            print("Groq rate limit hit, waiting 2 seconds and trying again...")
            time.sleep(2)


def extract_invoice_data_groq(text, missing_data):
    if not text:
        return {}

    prompt = make_prompt(text, missing_data)
    content = call_groq(prompt)

    if not content:
        return {}
    data = json.loads(content)
    if not isinstance(data, dict):
        return {}
    return data


def extract_invoice_data_gemini(text, missing_data):
    if not text:
        return {}

    prompt = make_prompt(text, missing_data)
    client = get_gemini_client()

    reply = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0,
        ),
    )

    if not reply.text:
        return {}
    data = json.loads(reply.text)
    if not isinstance(data, dict):
        return {}
    return data
