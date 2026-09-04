from sqlmodel import SQLModel,select,Session
from app.database import engine
from app.models import LineItem , Invoice


def create_invoice(vendor_name:str,amount:float,date:str):
    with Session(engine) as session:
        invoice=Invoice(vendor_name=vendor_name,amount=amount,date=date)
        session.add(invoice)
        session.commit()
        session.refresh(invoice)
        return invoice

def get_invoice(invoice_id:int):
    with Session(engine)as session:
        return session.get(Invoice,invoice_id)

def update_invoice(invoice_id:int,vendor_name:str=None,amount:float=None,date:str=None):
    with Session(engine)as session:
        invoice = session.get(Invoice,invoice_id)
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

print(delete_invoice(1))