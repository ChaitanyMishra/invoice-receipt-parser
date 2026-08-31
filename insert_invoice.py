from sqlmodel import Session
from app.models import Invoice, LineItem
from app.database import engine

with Session(engine) as session:
    invoice = Invoice(vendor_name="Chaitany", amount=25000.50, date="2026-08-30")
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    print(f"Inserted invoice with id: {invoice.id}")

    item1 = LineItem(invoice_id=invoice.id, item_name="Paper", amount=500.0)
    item2 = LineItem(invoice_id=invoice.id, item_name="Pens", amount=200.0)
    item3 = LineItem(invoice_id=invoice.id, item_name="Stapler", amount=150.0)

    session.add(item1)  
    session.add(item2)
    session.add(item3)
    session.commit()
    print(f"Created invoice {invoice.id} with 3 line items")