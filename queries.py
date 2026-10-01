from sqlmodel import Session, select,func
from app.database import engine
from app.models import Invoice,LineItem


def search_invoices(vendor_name:str=None , less_than:float=None, more_than:float=None, date:str=None):
    with Session(engine) as session:
        statment=select(Invoice)
        if vendor_name is not None:
            statment=statment.where(Invoice.vendor_name ==vendor_name)
        if less_than is not None:
            statment=statment.where(Invoice.amount<=less_than)
        if more_than is not None:
            statment=statment.where(Invoice.amount>=more_than)
        if date is not None:
            statment=statment.where(Invoice.date == date)
        result = session.exec(statment).all()
        return result

def search_line_items(item_name: str = None, min_amount: float = None, max_amount: float = None):
    with Session(engine) as session:
        statement = select(LineItem)
        if item_name is not None:
            statement = statement.where(LineItem.item_name == item_name)
        if min_amount is not None:
            statement = statement.where(LineItem.amount >= min_amount)
        if max_amount is not None:
            statement = statement.where(LineItem.amount <= max_amount)
        return session.exec(statement).all()


def get_invoice_total(invoice_id:int):
    with Session(engine) as session:
        statement= select(func.sum(LineItem.amount)).where(invoice_id==LineItem.invoice_id)
        result= session.exec(statement).all()
        return result


def get_invoice_lineitem_count(invoice_id:int):
    with Session(engine) as session:
        statement=select(func.count(LineItem.id)).where(LineItem.invoice_id==invoice_id)
        result=session.exec(statement).one()
        return result
    
print(get_invoice_lineitem_count(1))
print(get_invoice_total(1))

