import os
from sqlmodel import Session, select, delete

from app.database import engine
from app.models import Invoice, LineItem, UploadedFile, Batch


# FIX: accept user_id and store it on the record
def create_uploaded_file(
    filename: str,
    size: int,
    filepath: str,
    batch_id: int | None = None,
    user_id: int | None = None,
):
    with Session(engine) as session:
        record = UploadedFile(
            filename=filename,
            filepath=filepath,
            size=size,
            batch_id=batch_id,
            user_id=user_id,          # FIX
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


# FIX: optional user_id filter; None means "all files" (backwards compatible)
def files(user_id: int | None = None):
    with Session(engine) as session:
        statement = select(UploadedFile)
        if user_id is not None:
            statement = statement.where(UploadedFile.user_id == user_id)
        return session.exec(statement).all()


def _file_with_invoice(
    file: UploadedFile,
    invoice: Invoice | None,
    line_items: list[LineItem],
):
    file_data = file.model_dump(exclude={"filepath", "extracted_text"})
    file_data["has_extracted_text"] = bool(file.extracted_text)
    if invoice is None:
        file_data["invoice"] = None
        return file_data

    invoice_data = invoice.model_dump()
    invoice_data["line_items"] = [item.model_dump() for item in line_items]
    file_data["invoice"] = invoice_data
    return file_data


def get_files_with_invoices(user_id: int):
    with Session(engine) as session:
        uploaded_files = session.exec(
            select(UploadedFile)
            .where(UploadedFile.user_id == user_id)
            .order_by(UploadedFile.id)
        ).all()
        file_ids = [file.id for file in uploaded_files if file.id is not None]
        if not file_ids:
            return []

        invoices = session.exec(
            select(Invoice).where(Invoice.uploaded_file_id.in_(file_ids))
        ).all()
        invoices_by_file_id = {
            invoice.uploaded_file_id: invoice
            for invoice in invoices
            if invoice.uploaded_file_id is not None
        }
        invoice_ids = [invoice.id for invoice in invoices if invoice.id is not None]
        line_items_by_invoice_id: dict[int, list[LineItem]] = {}
        if invoice_ids:
            line_items = session.exec(
                select(LineItem).where(LineItem.invoice_id.in_(invoice_ids))
            ).all()
            for item in line_items:
                line_items_by_invoice_id.setdefault(item.invoice_id, []).append(item)

        file_data = []
        for file in uploaded_files:
            invoice = invoices_by_file_id.get(file.id)
            line_items = (
                line_items_by_invoice_id.get(invoice.id, [])
                if invoice is not None and invoice.id is not None
                else []
            )
            file_data.append(_file_with_invoice(file, invoice, line_items))
        return file_data


def get_file_with_invoice(file_id: int):
    with Session(engine) as session:
        file = session.get(UploadedFile, file_id)
        if not file:
            return None
        invoice = session.exec(
            select(Invoice).where(Invoice.uploaded_file_id == file_id)
        ).first()
        line_items = (
            session.exec(
                select(LineItem).where(LineItem.invoice_id == invoice.id)
            ).all()
            if invoice is not None and invoice.id is not None
            else []
        )
        return _file_with_invoice(file, invoice, line_items)


def get_file_by_id(id: int):
    with Session(engine) as session:
        return session.get(UploadedFile, id)


def update_file_status(file_id: int, status: str):
    with Session(engine) as session:
        file = session.get(UploadedFile, file_id)
        if not file:
            return None
        file.status = status
        session.commit()
        session.refresh(file)
        return file


def delete_file(id: int):
    filepath = None
    with Session(engine) as session:
        file = session.get(UploadedFile, id)
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
