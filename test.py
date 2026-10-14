# from app.services.pdf_extractor import extract_text_from_pdf
# from app.services.llm_extractor import extract_line_items_groq

# text = extract_text_from_pdf("uploads/invoice-2.pdf")
# print(extract_line_items_groq(text))


# from app.services.pdf_extractor import extract_text_from_pdf
# from app.services.invoice_parser import parse_invoice_text

# text = extract_text_from_pdf("/home/chaitany/Desktop/invoice_parser/uploads/invoice-2.pdf")
# parsed = parse_invoice_text(text)
# print(parsed)

# from app.services.pdf_extractor import extract_text_from_pdf
# from app.services.invoice_parser import parse_invoice_text

# text = extract_text_from_pdf("uploads/invoice-2.pdf")  # or your file
# parsed = parse_invoice_text(text)
# print("Parsed keys:", parsed.keys())
# print("Line items:", parsed.get("line_items"))
# print("Full parsed:", parsed)

from app.tasks import process_file

# Call the task synchronously (no queue, no worker)
# Bypasses .delay() — runs in the current process
process_file(1)   # ← use a real file_id from your DB
