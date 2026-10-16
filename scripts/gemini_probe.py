import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from app.services.llm_extractor import InvoiceData, GEMINI_MODEL

load_dotenv()
c = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
tests = {
    "plain": types.GenerateContentConfig(),
    "json": types.GenerateContentConfig(response_mime_type="application/json"),
    "thinking_budget=0": types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0)),
    "schema": types.GenerateContentConfig(
        response_mime_type="application/json", response_schema=InvoiceData),
}
for name, cfg in tests.items():
    try:
        r = c.models.generate_content(
            model=GEMINI_MODEL, contents='Return {"a": 1} as JSON', config=cfg)
        print(f"{name}: OK {r.text[:40]!r}")
    except Exception as e:
        print(f"{name}: FAIL {str(e)[:150]}")
