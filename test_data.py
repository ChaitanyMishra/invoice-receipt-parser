# from sqlmodel import Session
# from app.database import engine
# from app.models import Invoice, LineItem

# with Session(engine) as session:
#     inv1 = Invoice(vendor_name="ABC Traders", amount=850.0, date="2026-09-06")
#     session.add(inv1)
#     session.commit()
#     session.refresh(inv1)

#     inv2 = Invoice(vendor_name="XYZ Supplies", amount=450.0, date="2026-09-06")
#     session.add(inv2)
#     session.commit()
#     session.refresh(inv2)

#     items = [
#         LineItem(invoice_id=inv1.id, item_name="Paper", amount=500.0),
#         LineItem(invoice_id=inv1.id, item_name="Pens", amount=200.0),
#         LineItem(invoice_id=inv1.id, item_name="Stapler", amount=150.0),
#         LineItem(invoice_id=inv2.id, item_name="Ink Cartridge", amount=300.0),
#         LineItem(invoice_id=inv2.id, item_name="Notebooks", amount=150.0),
#     ]
# with Session(engine) as session:
#     lonely_invoice = Invoice(vendor_name="No Items Co", amount=0.0, date="2026-09-07")
#     session.add(lonely_invoice)
#     session.commit()
#     session.refresh(lonely_invoice)
#     print(f"Created invoice {lonely_invoice.id} with ZERO line items")
#     # for item in items:
#     #     session.add(item)
#     # session.commit()

#     # print(f"Created Invoice {inv1.id} ({inv1.vendor_name}) and Invoice {inv2.id} ({inv2.vendor_name})")


# from sqlmodel import Session, select
# from app.database import engine
# from app.models import Invoice
# import datetime

# with Session(engine) as session:
#     statement = select(Invoice).where(
#         Invoice.date >= datetime.date(2026, 1, 1),
#         Invoice.date <= datetime.date(2026, 12, 31)
#     )
#     results = session.exec(statement).all()
#     for inv in results:
#         print(inv.vendor_name, inv.date)

from sqlmodel import Session
from app.database import engine
from app.models import Invoice, LineItem
import datetime

data = [
    {"vendor_name": "ABC Traders", "amount": 500, "date": datetime.date(2026, 1, 15),
     "items": [{"item_name": "Paper", "amount": 500}]},
    # ... more entries
]

with Session(engine) as session:
    for entry in data:
        invoice = Invoice(vendor_name=entry["vendor_name"], amount=entry["amount"], date=entry["date"])
        session.add(invoice)
        session.commit()
        session.refresh(invoice)
        for item in entry["items"]:
            line_item = LineItem(invoice_id=invoice.id, item_name=item["item_name"], amount=item["amount"])
            session.add(line_item)
    session.commit()