from pathlib import Path
import pdfplumber

def extract_text_from_pdf(filepath: str) -> str | None:
    file = Path(filepath)
    file_type = file.suffix
    if file_type.lower() != ".pdf":
        return None
    all_text = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text.append(text)

            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    clean_row = [str(cell).strip() if cell else "" for cell in row]
                    row_text = " | ".join(clean_row)
                    if row_text.strip(" |"):
                        all_text.append(row_text)

    if not all_text:
        return None

    return "\n".join(all_text)
