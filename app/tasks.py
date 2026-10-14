from sqlmodel import Session , select
from app.database import engine
from app.models import Batch, UploadedFile
from app.celery_app import celery_app
from app.services.pdf_extractor import extract_text_from_pdf
from app.services.invoice_parser import parse_invoice_text
from crud_invoice import create_invoice

@celery_app.task
def process_file(file_id:int):
    with Session(engine) as session:
        file = session.get(UploadedFile,file_id)
        if not file:
            print(f"Task {file_id}: UploadedFile not found")
            return None

        batch = None
        if file.batch_id:
            batch = session.get(Batch,file.batch_id)

        file.status ='processing'
        session.commit()

        try:

            text = file.extracted_text
            if not text:
            # extracted_text = extract_text_from_pdf(file.filepath)
                text = extract_text_from_pdf(file.filepath)
                file.extracted_text = text

            parsed_text = parse_invoice_text(text)

            create_invoice(parsed_text,file_id)


            file.status = "completed"
            if batch:
                batch.completed_files += 1
            print(f"Task file_id={file_id}: completed")

        except Exception as e:
            file.status='failed'
            if batch:
                batch.failed_files+=1
                print(f"Task file_id={file_id} failed: {e}")

        if batch:
            done = batch.completed_files+batch.failed_files
            if done >= batch.total_files:
                batch.status='completed' if batch.failed_files == 0  else  'partial'
            else:
                batch.status='processing'

        session.commit()








