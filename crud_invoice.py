from sqlmodel import SQLModel,select,Session
from app.database import engine
from typing import Optional
from app.models import LineItem , Invoice
import datetime

def create_invoice(vendor_name:str,amount:float,date:datetime.date,status:str,items:list[dict]):
    with Session(engine) as session:
        invoice=Invoice(vendor_name=vendor_name,amount=amount,status=status,date=date)
        session.add(invoice)
        session.commit()
        session.refresh(invoice)

        for item in items:
            line_item=LineItem(invoice_id=invoice.id,item_name=item["item_name"],amount=item["amount"])
            session.add(line_item)
        session.commit()
        return invoice

def get_invoice(invoice_id:int) -> Optional[Invoice]:
    with Session(engine)as session:
        return session.get(Invoice,invoice_id)

def update_invoice(invoice_id:int,vendor_name:str=None,amount:float=None,date:str=None) -> Optional[Invoice]:
    with Session(engine)as session:
        invoice = session.get(Invoice,invoice_id)
        if not invoice:
            return None
        if vendor_name is not None:
            invoice.vendor_name=vendor_name
        if amount is not None:
            invoice.amount=amount
        if date is not None:
            invoice.date=date
        session.commit()
        return invoice

def delete_invoice(invoice_id:int):
    with Session(engine) as session:
        invoice = session.get(Invoice,invoice_id)
        if not invoice:
            return f"Invoice {invoice_id} not found."
        statment = select(LineItem).where(LineItem.invoice_id == invoice_id)
        lineItem=session.exec(statment).all()
        print(f"Found {len(lineItem)} line items to delete")
        for item in lineItem:
            print(f"Deleting: {item}")
            session.delete(item)
        session.flush()

        session.delete(invoice)
        session.commit()
        return f"Deleted Sucessfully!"

if __name__ == "__main__":
    print(delete_invoice(1))
    create_invoice("Test Multi Vendor", 1500, datetime.date(2026, 2, 1), "pending",
    [{"item_name": "A", "amount": 500},
     {"item_name": "B", "amount": 600},
     {"item_name": "C", "amount": 400}])