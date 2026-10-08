from sqlmodel import Session, select
from app.database import engine
import os
from app.models import UploadedFile


def create_uploaded_file(filename: str, size: int, filepath: str):
    with Session(engine) as session:
        record = UploadedFile(filename=filename, filepath=filepath, size=size)
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
        statement = select(UploadedFile).where(UploadedFile.id == id)
        result = session.exec(statement)
        file = result.first()
        if not file:
            return None

        filepath = file.filepath
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
