import os
from sqlmodel import Session, select,delete

from app.database import engine
from app.models import Invoice, LineItem, UploadedFile,Batch


def create_uploaded_file(filename: str, size: int, filepath: str, batch_id:int=None):
    with Session(engine) as session:
        record = UploadedFile(filename=filename, filepath=filepath, size=size , batch_id=batch_id)
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def files():
    with Session(engine) as session:
        statment = select(UploadedFile)
        table_data = session.exec(statment).all()
        return table_data


def get_file_by_id(id: int):
    with Session(engine) as session:
        files = session.get(UploadedFile, id)
        return files


def delete_file(id: int):
    filepath = None
    with Session(engine) as session:
        file = session.get(UploadedFile,id)
        if not file:
            return None

        filepath = file.filepath
        inv = select(Invoice).where(Invoice.uploaded_file_id == id)
        res = session.exec(inv).first()
        if res:
            session.exec(delete(LineItem).where(LineItem.invoice_id == res.id))
            session.delete(res)
            session.flush()
        session.delete(file)
        session.commit()
    try:
        os.remove(filepath)
    except FileNotFoundError:
        return {"status": "deleted", "note": "file was already missing from disk"}

    return {"status": "deleted successfully"}


def update_extracted_text(file_id: int, text: str | None):
    if not text:
        return None
    with Session(engine) as session:
        file = session.get(UploadedFile, file_id)
        if not file:
            return None
        file.extracted_text = text
        session.commit()
        session.refresh(file)
    return file

