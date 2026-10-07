from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
load_dotenv()
from app.services.pdf_extractor import extract_text_from_pdf
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

def test_api(invoice_text:str):
    prompt = f'''
    Extract vendor_name and address from this invoice text.

    Return JSON with keys "vendor_name" and "address".
    If a field is not found, use null.

    Invoice Text : {invoice_text}
    '''
    if not invoice_text:
        return None
    response =  client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type='application/json'),
        )
    return response.text
text = extract_text_from_pdf('/home/chaitany/Desktop/invoice_parser/uploads/invoice.pdf')

print( test_api(text))

