import os
import redis
from sqlmodel import Session, update
from app.database import engine
from app.models import Batch, UploadedFile
from app.celery_app import celery_app
from app.services.pdf_extractor import extract_text_from_pdf
from app.services.invoice_parser import parse_invoice_text
from crud_invoice import create_invoice

redis_client = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
)


@celery_app.task(
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def process_file(file_id: int):
    with Session(engine) as session:
        file = session.get(UploadedFile, file_id)
        if not file:
            print(f"Task {file_id}: UploadedFile not found")
            return {"status": "not_found", "file_id": file_id}

        batch = None
        if file.batch_id:
            batch = session.get(Batch, file.batch_id)

        file.status = "processing"
        session.commit()
        if redis_client:
            try:
                redis_client.delete(f"my_files:user:{file.user_id}")
            except redis.exceptions.RedisError:
                pass

        try:
            text = file.extracted_text
            if not text:
                text = extract_text_from_pdf(file.filepath)
                file.extracted_text = text

            if not text:
                file.status = "failed"
                if batch:
                    session.exec(
                        update(Batch)
                        .where(Batch.id == batch.id)
                        .values(failed_files=Batch.failed_files + 1)
                    )
                session.commit()
                return {"status": "failed", "file_id": file_id, "reason": "No text extracted."}

            parsed_text = parse_invoice_text(text)
            create_invoice(parsed_text, file_id)

            file.status = (
                "review" if parsed_text.get("validation_warnings") else "completed"
            )
            if batch:
                session.exec(
                    update(Batch)
                    .where(Batch.id == batch.id)
                    .values(completed_files=Batch.completed_files + 1)
                )

            if batch:
                session.refresh(batch)
                done = batch.completed_files + batch.failed_files
                if done >= batch.total_files:
                    batch.status = "completed" if batch.failed_files == 0 else "partial"
                else:
                    batch.status = "processing"

            print(f"Task file_id={file_id}: completed")
            session.commit()
            return {"status": file.status, "file_id": file_id, "invoice_data": parsed_text}

        except (ConnectionError, TimeoutError):
            raise

        except Exception as e:
            session.rollback()
            file.status = "failed"
            if batch:
                session.exec(
                    update(Batch)
                    .where(Batch.id == batch.id)
                    .values(failed_files=Batch.failed_files + 1)
                )
            print(f"Task file_id={file_id} failed: {e}")
            if batch:
                session.refresh(batch)
                done = batch.completed_files + batch.failed_files
                if done >= batch.total_files:
                    batch.status = "completed" if batch.failed_files == 0 else "partial"
                else:
                    batch.status = "processing"
            session.commit()
            return {"status": "failed", "file_id": file_id, "error": str(e)}
        finally:
            if redis_client:
                try:
                    redis_client.delete(f"my_files:user:{file.user_id}")
                except redis.exceptions.RedisError:
                    pass


