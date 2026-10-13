from app.services.pdf_extractor import extract_text_from_pdf
from app.services.llm_extractor import extract_line_items_groq

text = extract_text_from_pdf("uploads/invoice.pdf")
print(extract_line_items_groq(text))
