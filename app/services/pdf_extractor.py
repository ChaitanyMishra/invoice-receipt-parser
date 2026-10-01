import pdfplumber
from pathlib import Path
def extract_text_from_pdf(filepath:str) ->str| None:
    file = Path(filepath)
    file_type = file.suffix
    if file_type.lower() != '.pdf':
        return None
    all_text = []
    with pdfplumber.open(filepath) as pdf:
        
        for i,page in enumerate(pdf.pages,start=1):
            text = page.extract_text()
            if text:
                all_text.append(text)

    if not all_text:
        return None
    return '\n'.join(all_text)

            
