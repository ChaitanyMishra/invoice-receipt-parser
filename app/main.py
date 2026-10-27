from contextlib import asynccontextmanager
import io
from openpyxl import Workbook
from fastapi.responses import StreamingResponse
import json
import os
import re
import uuid

import redis
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from sqlmodel import SQLModel
from tomlkit import ws
from crud_invoice import get_invoice_by_id
from contextlib import asynccontextmanager
from app.auth import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_hash_password,
)
from app.database import engine
from app.models import User
from app.services.invoice_parser import parse_invoice_text
from app.services.pdf_extractor import extract_text_from_pdf
from app.tasks import process_file
from crud_batch import create_batch
from crud_invoice import create_invoice
from crud_uploaded_file import (
    create_uploaded_file,
    delete_file,
    files,
    get_file_by_id,
    update_extracted_text,
)
from crud_user import create_user, get_user_by_email

load_dotenv()

class UserRegister(BaseModel):
    email: EmailStr
    password: str

redis_client = redis.Redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)  # type: ignore

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

@asynccontextmanager
async def lifespan(app:FastAPI):
    SQLModel.metadata.create_all(bind=engine)
    yield


def invoice_count(text: str):
    patterns = [
        r"Invoice Number\s*:\s*(\S+)",
        r"Invoice No\.?\s*Dated\s*[\r\n]+\s*(\S+)",
        r"Invoice No\.?\s*[\r\n]+\s*([\w/]+-\d+)",
        r"Bill No\.?\s*:?\s*(\S+)",
    ]
    unique_match = set()
    for pattern in patterns:
        for m in re.findall(pattern, text, flags=0):
            unique_match.add(m)
    if len(unique_match) > 1:
        return False
    return True



def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    valid_user = decode_access_token(token)
    if not valid_user:
        raise HTTPException(status_code=401, detail="Unauthorized user")
    user_mail = valid_user.get("email")
    user = get_user_by_email(user_mail)
    if not user:
        raise HTTPException(status_code=401, detail="user not exists")
    return user


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/files")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    ALLOWED = {"image/jpeg", "image/png", "application/pdf"}
    if file.content_type not in ALLOWED:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, PDF allowed")

    read_file = await file.read()
    filename = file.filename or "unnamed_file"
    filepath = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{filename}")

    with open(filepath, "wb") as f:
        f.write(read_file)

    record = create_uploaded_file(
        filename=filename,
        size=len(read_file),
        filepath=filepath,
        user_id=current_user.id
    )
    # FIX: Clear only this user's cache
    redis_client.delete(f"my_files:user:{current_user.id}")
    return {"id": record.id, "filename": filename, "size": len(read_file)}


@app.get("/get_upload_data")
def get_documents(current_user: User = Depends(get_current_user)):
    cache_key = f"my_files:user:{current_user.id}"
    redis_cache = redis_client.get(cache_key)
    if redis_cache:
        print("CACHE HIT")
        return json.loads(redis_cache)

    print("CACHE MISS")

    db_files = files(user_id=current_user.id)
    file_list = [f.model_dump() for f in db_files]
    redis_client.set(cache_key, json.dumps(file_list, default=str), ex=60)

    return file_list


@app.get("/files/{file_id}")
def get_file(file_id: int , current_user:User=Depends(get_current_user)):
    file = get_file_by_id(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="file not found")
    if file.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this file")
    return file


@app.delete("/files/{file_id}")
def del_file(file_id: int, current_user:User=Depends(get_current_user)):
    file = get_file_by_id(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="file not found")
    if file.user_id != current_user.id:
        raise HTTPException(status_code=403,detail='Not Authorize')
    res = delete_file(file_id)
    if not res:
        raise HTTPException(status_code=404, detail="file not found")
    redis_client.delete(f"my_files:user:{current_user.id}")

    return res


@app.post("/files/{file_id}/extract")
def extract_file(file_id: int , current_user:User=Depends(get_current_user)):
    file = get_file_by_id(file_id)
    if not file:
            raise HTTPException(status_code=404, detail="file not found")
    if file.user_id != current_user.id:
        raise HTTPException(status_code=403,detail="Not Authorized")


    extracted_text = extract_text_from_pdf(file.filepath)
    if not extracted_text:
        return {
            "status": "no_text_extracted",
            "file_id": file_id,
            "note": "File has no extractable text. Likely scanned PDF or image.",
        }
    update_extracted_text(file_id, extracted_text)
    redis_client.delete(f"my_files:user:{current_user.id}")

    return {
        "status": "extracted",
        "file_id": file_id,
        "length": len(extracted_text),
        "preview": extracted_text[:200],
    }


@app.post("/files/{file_id}/parse")
def parse_file(file_id: int , current_user:User=Depends(get_current_user)):
    file = get_file_by_id(file_id)
    if not file:
            raise HTTPException(status_code=404, detail="File or extracted text not found")
    if file.user_id != current_user.id:
        raise HTTPException(status_code=403,detail='Not Authorized')
    if not file.extracted_text:
        raise HTTPException(status_code=404, detail="Extracted text not found")

    if not invoice_count(file.extracted_text):
        raise HTTPException(
            status_code=400, detail="pdf contains more than 1 invoice"
        )
    parsed_dict = parse_invoice_text(file.extracted_text)
    if not parsed_dict:
        raise HTTPException(status_code=400, detail="Failed to parse invoice data")

    invoice_id = create_invoice(parsed_dict, file_id)
    redis_client.delete(f"my_files:user:{current_user.id}")
    return {
        "status": "parsed",
        "invoice_id": invoice_id,
        "parsed_data": parsed_dict,
    }


@app.post("/batch-upload")
async def batch_upload(
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user)
):
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

        # FIX: Save user_id
        file_id = create_uploaded_file(
            filename=filename,
            size=len(read_file),
            filepath=filepath,
            batch_id=batch_id,
            user_id=current_user.id
        ).id
        upload_file_ids.append(file_id)
        redis_client.delete(f"my_files:user:{current_user.id}")

    for file_id in upload_file_ids:
        process_file.delay(file_id)

    return {"batch_id": batch_id, "total_files": len(files), "status": "queued"}


@app.post("/register", status_code=201)
def register_user(user_data: UserRegister):
    existing_user = get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(status_code=409, detail="user already exists")
    hashed_password = get_password_hash(user_data.password)

    new_user = create_user(user_data.email, hashed_password)  # type: ignore
    if new_user:
        return {"message": "registration successful!", "user_id": new_user.id}


@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    existing_user = get_user_by_email(form_data.username)
    if not existing_user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    is_valid = verify_hash_password(form_data.password, existing_user.hashed_password)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    access_token = create_access_token({"email": existing_user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get('/invoices/export')
def export_invoice(current_user:User=Depends(get_current_user)):
    invoices = get_invoice_by_id(current_user.id)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Invoices'
    ws.append(["Invoice ID", "Vendor", "Invoice Number", "GSTIN" ,  "Address" , "Date", "Total", "Tax", "Status"])

    for inv in invoices:
        ws.append([
            inv.id,
            inv.vendor_name or  "",
            inv.invoice_number or "",
            inv.gstin or "",
            inv.address or "",
            inv.date or "",
            inv.total or 0.0,
            inv.tax_amount or 0.0,
            inv.status
        ])
    buffer  = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return StreamingResponse(buffer,media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition": 'attachment; filename="invoices_export.xlsx"'})
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
