import datetime

from sqlmodel import Session, select, delete

from app.database import engine
from app.models import Invoice, LineItem

# from app.services.llm_extractor import extract_missing_data_groq,extract_missing_data


def create_invoice(parsed_data: dict, uploaded_file_id: int):
    date_str = parsed_data.get("date")
    parsed_date = (
        datetime.datetime.strptime(date_str, "%d.%m.%Y").date() if date_str else None
    )
    total_str = parsed_data.get("total")
    total_amount = float(total_str) if total_str else None
    tax_str = parsed_data.get("tax_amount")
    total_tax = float(tax_str) if tax_str else None
    sub_total = (
        (total_amount - total_tax)
        if (total_amount is not None and total_tax is not None)
        else None
    )
    line_items = parsed_data.get("line_items", [])
    # address = parsed_data.get("address")
    with Session(engine) as session:
        existing = session.exec(select(Invoice).where(Invoice.uploaded_file_id == uploaded_file_id)).first()

        if existing:
            if total_amount is not None:
                existing.total = total_amount
            if total_tax is not None:
                existing.tax_amount = total_tax
            if parsed_date is not None:
                existing.date = parsed_date
            if parsed_data.get("invoice_number"):
                existing.invoice_number = parsed_data["invoice_number"]
            if parsed_data.get("gstin"):
                existing.gstin = parsed_data["gstin"]
            if parsed_data.get("order_number"):
                existing.order_number = parsed_data["order_number"]
            if parsed_data.get("vendor_name"):
                existing.vendor_name = parsed_data["vendor_name"]
            if sub_total is not None:
                existing.subtotal = sub_total
            if parsed_data.get("address"):
                existing.address = parsed_data["address"]
            session.exec(delete(LineItem).where(LineItem.invoice_id == existing.id))
            for item in line_items:
                line_item = LineItem(
                    invoice_id=existing.id,
                    description=item["description"],
                    amount=item["amount"],
                    unit_price=float(item["unit_price"])
                    if item.get("unit_price") is not None
                    else None,

                    quantity=float(item["quantity"])
                    if item.get("quantity") is not None
                    else None,
                )
                session.add(line_item)
            session.commit()
            session.refresh(existing)
            return existing.id
        invoice = Invoice(
            total=float(parsed_data.get("total")) if parsed_data.get("total") else None,
            tax_amount=(
                parsed_data.get("tax_amount") if parsed_data.get("tax_amount") else None
            ),
            order_number=parsed_data.get("order_number"),
            invoice_number=parsed_data.get("invoice_number"),
            date=parsed_date,
            address=parsed_data.get("address") if parsed_data.get("address") else None,
            gstin=parsed_data.get("gstin"),
            uploaded_file_id=uploaded_file_id,
            vendor_name=(
                parsed_data.get("vendor_name")
                if parsed_data.get("vendor_name")
                else None
            ),
            status="completed",
            subtotal=sub_total,
        )
        session.add(invoice)
        session.commit()
        session.refresh(invoice)

        for item in line_items:
            items = LineItem(
                invoice_id=invoice.id,
                description=item["description"],
                amount=item["amount"],
                unit_price=float(item["unit_price"]) if item.get("unit_price") is not None else None,
                quantity=float(item["quantity"]) if item.get("quantity") is not None else None,
            )
            session.add(items)
        session.commit()
        return invoice.id


def get_invoice(invoice_id: int) -> Invoice | None:
    with Session(engine) as session:
        return session.get(Invoice, invoice_id)


def update_invoice(
    invoice_id: int, vendor_name: str = None, amount: float = None, date: str = None
) -> Invoice | None:
    with Session(engine) as session:
        invoice = session.get(Invoice, invoice_id)
        if not invoice:
            return None
        if vendor_name is not None:
            invoice.vendor_name = vendor_name
        if amount is not None:
            invoice.total = amount
        if date is not None:
            invoice.date = date
        session.commit()
        return invoice


def delete_invoice(invoice_id: int):
    with Session(engine) as session:
        invoice = session.get(Invoice, invoice_id)
        if not invoice:
            return f"Invoice {invoice_id} not found."
        statment = select(LineItem).where(LineItem.invoice_id == invoice_id)
        lineItem = session.exec(statment).all()
        print(f"Found {len(lineItem)} line items to delete")
        for item in lineItem:
            print(f"Deleting: {item}")
            session.delete(item)
        session.flush()

        session.delete(invoice)
        session.commit()
        return "Deleted Sucessfully!"

