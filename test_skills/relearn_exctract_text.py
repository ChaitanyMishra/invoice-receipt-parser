import pdfplumber
from pathlib import Path

def extract_text(file_path:str)->None:
    text=[]
    file = Path(file_path)
    file_type = file.suffix
    if file_type.lower() != '.pdf':
        return None
    
    with pdfplumber.open(file) as pdf:
        for i,page in enumerate(pdf.pages,start=1):
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)

    if not text:
        return None
    return '\n'.join(text)

print(extract_text('/home/chaitany/Desktop/invoice_parser/uploads/invoice.pdf'))