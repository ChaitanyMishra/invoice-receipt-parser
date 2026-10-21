import os
import uuid
import re
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from app.database import engine
from sqlmodel import SQLModel
from app.tasks import process_file
from app.services.invoice_parser import parse_invoice_text,extract_field
from app.services.pdf_extractor import extract_text_from_pdf
from crud_batch import create_batch
from crud_invoice import create_invoice
from crud_uploaded_file import (
    create_uploaded_file,
    delete_file,
    files,
    get_file_by_id,
    update_extracted_text,
)
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()

@app.on_event("startup")
def startup():
    SQLModel.metadata.create_all(bind=engine)

def invoice_count(text:str):
    patterns = [
        r"Invoice Number\s*:\s*(\S+)",                      # Amazon
        r"Invoice No\.?\s*Dated\s*[\r\n]+\s*(\S+)",         # Supercloud (with "Dated" label)
        r"Invoice No\.?\s*[\r\n]+\s*([\w/]+-\d+)",          # Supercloud (no "Dated")
        r"Bill No\.?\s*:?\s*(\S+)",
        ]
    unique_match = set()

    for pattern in patterns:
        for m in (re.findall(pattern , text ,flags=0)):
            unique_match.add(m)

    if len(unique_match) > 1:
        return False
    return True

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/files")
async def upload_file(file: UploadFile = File(...)):
    ALLOWED = {"image/jpeg", "image/png", "application/pdf"}
    if file.content_type not in ALLOWED:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, PDF allowed")

    read_file = await file.read()
    filename = file.filename or "unnamed_file"

    # FIXED: Added UUID prefix to prevent file overwriting collisions
    filepath = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{filename}")

    with open(filepath, "wb") as f:
        f.write(read_file)

    record = create_uploaded_file(
        filename=filename, size=len(read_file), filepath=filepath
    )
    return {"id": record.id, "filename": filename, "size": len(read_file)}


@app.get("/get_upload_data")
def get_documents():
    return files()


@app.get("/files/{file_id}")
def get_file(file_id: int):
    file = get_file_by_id(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="file not found")
    return file


@app.delete("/files/{file_id}")
def del_file(file_id: int):
    res = delete_file(file_id)
    if not res:
        raise HTTPException(status_code=404, detail="file not found")
    return res


@app.post("/files/{file_id}/extract")
def extract_file(file_id: int):
    file = get_file_by_id(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="file not found")

    extracted_text = extract_text_from_pdf(file.filepath)
    if not extracted_text:
        return {
            "status": "no_text_extracted",
            "file_id": file_id,
            "note": "File has no extractable text. Likely scanned PDF or image.",
        }
    update_extracted_text(file_id, extracted_text)

    return {
        "status": "extracted",
        "file_id": file_id,
        "length": len(extracted_text),
        "preview": extracted_text[:200],
    }


@app.post("/files/{file_id}/parse")
def parse_file(file_id: int):
    file = get_file_by_id(file_id)
    if not file or not file.extracted_text:
        raise HTTPException(status_code=404, detail="File or extracted text not found")

    if not invoice_count(file.extracted_text):
            raise HTTPException(status_code=400,detail='pdf contains more than 1  invoice  ')
    parsed_dict = parse_invoice_text(file.extracted_text)
    if not parsed_dict:
        raise HTTPException(status_code=400, detail="Failed to parse invoice data")

    invoice_id = create_invoice(parsed_dict, file_id)
    return {
        "status": "parsed",
        "invoice_id": invoice_id,
        "parsed_data": parsed_dict,
    }


@app.post("/batch-upload")
async def batch_upload(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    batch_id = create_batch(len(files))
    upload_file_ids = []

    for file in files:
        filename = file.filename or "unnamed_file"
        filepath = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{filename}")
        read_file = await file.read()

        with open(filepath, "wb") as f:
            f.write(read_file)

        file_id = create_uploaded_file(
            filename=filename, size=len(read_file), filepath=filepath, batch_id=batch_id
        ).id
        upload_file_ids.append(file_id)

    for file_id in upload_file_ids:
        process_file.delay(file_id)

    return {"batch_id": batch_id, "total_files": len(files), "status": "queued"}


# Static files mounted last so API routes take precedence
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
# this is a test comment
