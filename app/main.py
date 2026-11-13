from contextlib import asynccontextmanager
import io
from openpyxl import Workbook
from fastapi.responses import StreamingResponse
import json
import os
import uuid
import logging
import re

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

import redis
from celery.result import AsyncResult
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, SQLModel, select
from crud_batch import create_batch
from crud_invoice import get_invoice_by_id
from app.auth import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_hash_password,
)
from app.celery_app import celery_app
from app.database import engine
from app.models import Batch, UploadedFile, User
from app.services.invoice_parser import parse_invoice_text
from app.services.pdf_extractor import extract_text_from_pdf
from crud_invoice import create_invoice
from crud_uploaded_file import (
    create_uploaded_file,
    delete_file,
    get_files_with_invoices,
    get_file_with_invoice,
    get_file_by_id,
    update_extracted_text,
)
from crud_user import create_user, get_user_by_email

load_dotenv()

class UserRegister(BaseModel):
    email: EmailStr
    password: str

redis_client = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
)

UPLOAD_DIR = "uploads"
PARSE_LIMIT = 50
PARSE_WINDOW_SECONDS = 60
os.makedirs(UPLOAD_DIR, exist_ok=True)


def safe_redis_delete(key: str):
    if not redis_client:
        return False
    try:
        return bool(redis_client.delete(key))
    except redis.exceptions.RedisError:
        return False


def safe_redis_get(key: str):
    if not redis_client:
        return None
    try:
        return redis_client.get(key)
    except redis.exceptions.RedisError:
        return None


def safe_redis_set(key: str, value: str, ex: int | None = None):
    if not redis_client:
        return False
    try:
        if ex is not None:
            return redis_client.set(key, value, ex=ex)
        return redis_client.set(key, value)
    except redis.exceptions.RedisError:
        return False

@asynccontextmanager
async def lifespan(app:FastAPI):
    SQLModel.metadata.create_all(bind=engine)
    yield

app = FastAPI(lifespan=lifespan)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


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
        logger.warning(f"Failed log in attempt for token")
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
    logger.info(f"User {current_user.id} uploaded {filename}")
    safe_redis_delete(f"my_files:user:{current_user.id}")
    return {"id": record.id, "filename": filename, "size": len(read_file)}


@app.get("/get_upload_data")
def get_documents(current_user: User = Depends(get_current_user)):
    cache_key = f"my_files:user:{current_user.id}"
    redis_cache = None
    if redis_client:
        try:
            redis_cache = redis_client.get(cache_key)
        except redis.exceptions.RedisError:
            redis_cache = None
    if redis_cache:
        logger.info("CACHE HIT")
        return json.loads(redis_cache)
    logger.info("CACHE MISS")
    file_list = get_files_with_invoices(current_user.id)
    if redis_client:
        try:
            redis_client.set(cache_key, json.dumps(file_list, default=str), ex=60)
        except redis.exceptions.RedisError:
            pass

    return file_list


@app.get("/files/{file_id}")
def get_file(file_id: int , current_user:User=Depends(get_current_user)):
    file = get_file_by_id(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="file not found")
    if file.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this file")
    return get_file_with_invoice(file_id)


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
    safe_redis_delete(f"my_files:user:{current_user.id}")

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
    safe_redis_delete(f"my_files:user:{current_user.id}")

    return {
        "status": "extracted",
        "file_id": file_id,
        "length": len(extracted_text),
        "preview": extracted_text[:200],
    }


@app.post("/files/{file_id}/parse")
def parse_file(file_id: int ,  force_llm: bool = False, current_user:User=Depends(get_current_user)):
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

    rate_limit_key = f"rate_limit:parse:{current_user.id}"
    current_count = None
    if redis_client:
        try:
            current_count = redis_client.get(rate_limit_key)
        except redis.exceptions.RedisError:
            current_count = None

    if current_count and int(current_count) >= PARSE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again in a minute."
        )
    if redis_client:
        try:
            redis_client.incr(rate_limit_key)
            if not current_count:
                redis_client.expire(rate_limit_key, PARSE_WINDOW_SECONDS)
        except redis.exceptions.RedisError:
            pass

    logger.info(f"Parsing file {file_id} for user {current_user.id} (Force LLM: {force_llm})")

    # FIX: Actually pass force_llm down to the parser
    parsed_dict = parse_invoice_text(file.extracted_text, force_llm=force_llm)

    if not parsed_dict:
        raise HTTPException(status_code=400, detail="Failed to parse invoice data")

    invoice_id = create_invoice(parsed_dict, file_id)
    safe_redis_delete(f"my_files:user:{current_user.id}")
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
    created_files = []
    task_ids = []

    for file in files:
        filename = file.filename or "unnamed_file"
        filepath = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{filename}")
        read_file = await file.read()

        with open(filepath, "wb") as f:
            f.write(read_file)

        record = create_uploaded_file(
            filename=filename,
            size=len(read_file),
            filepath=filepath,
            batch_id=batch_id,
            user_id=current_user.id
        )
        created_files.append(record.id)

        task = celery_app.send_task("app.tasks.process_file", args=[record.id])
        safe_redis_set(f"task_owner:{task.id}", str(current_user.id))
        task_ids.append(task.id)
        safe_redis_delete(f"my_files:user:{current_user.id}")

    with Session(engine) as session:
        batch = session.get(Batch, batch_id)
        if batch:
            batch.status = "processing"
            session.commit()

    return {
        "total_files": len(files),
        "batch_id": batch_id,
        "status": "processing",
        "file_ids": created_files,
        "task_ids": task_ids,
    }


@app.get("/batch/{batch_id}")
def get_batch(batch_id: int, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        batch = session.get(Batch, batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="batch not found")

        files = session.exec(
            select(UploadedFile).where(UploadedFile.batch_id == batch_id)
        ).all()
        owned_files = [file for file in files if file.user_id == current_user.id]
        if not owned_files and batch.id is not None:
            raise HTTPException(status_code=403, detail="Not Authorized")

        return {
            "batch_id": batch.id,
            "status": batch.status,
            "total_files": batch.total_files,
            "completed_files": batch.completed_files,
            "failed_files": batch.failed_files,
            "files": [file.id for file in owned_files],
        }


@app.post("/files/{file_id}/queue")
def queue_file_processing(file_id: int, current_user: User = Depends(get_current_user)):
    file = get_file_by_id(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="file not found")
    if file.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not Authorized")

    task = celery_app.send_task("app.tasks.process_file", args=[file_id])
    safe_redis_set(f"task_owner:{task.id}", str(current_user.id))
    return {
        "task_id": task.id,
        "file_id": file_id,
        "status": "queued",
    }


@app.get("/tasks/{task_id}")
def get_task_status(task_id: str, current_user: User = Depends(get_current_user)):
    owner_id = safe_redis_get(f"task_owner:{task_id}")
    if owner_id is not None and int(owner_id) != current_user.id:
        raise HTTPException(status_code=403, detail="Not Authorized")

    result = AsyncResult(task_id, app=celery_app)
    response = {
        "task_id": task_id,
        "status": result.status,
        "result": result.result,
    }
    if result.status in {"SUCCESS", "FAILURE"}:
        safe_redis_delete(f"task_owner:{task_id}")
    return response


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

SQLModel.metadata.create_all(bind=engine)

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
