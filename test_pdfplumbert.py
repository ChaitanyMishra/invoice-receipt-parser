import pdfplumber
from pathlib import Path

# extract file
file = Path('/home/chaitany/Desktop/invoice_parser/uploads/Order Details.pdf')
filetype = (file.suffix).lower()
if filetype != '.pdf':
    print(f'{file.name} is not a pdf')
    exit()


with pdfplumber.open(file) as pdf:
    total_char=0
    for i ,page in enumerate(pdf.pages,start=1):
        text = page.extract_text()
        if text is None:
            print('pdf is empty')
            continue
        total_char+=len(text)
        print(f'-----{i}------')
        print(text)
    print(f"\nTotal characters extracted: {total_char}")