from app.database import engine
from sqlmodel import Session
from app.models import Batch, UploadedFile

def create_batch(total_files:int):
    with Session(engine) as session:
        batch = Batch(total_files=total_files,completed_files=0,failed_files=0,status='pending')
        session.add(batch)
        session.commit()
        session.refresh(batch)
        return batch.id
