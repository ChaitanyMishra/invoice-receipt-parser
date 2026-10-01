# from sqlmodel import select,and_,Session
# from sqlalchemy import outerjoin
# from app.database import engine
# from app.models import LineItem, Invoice
# from crud_invoice import create_invoice


# # invoice = create_invoice(vendor_name="Shiva Traders",amount=850.0,date="2026-09-06")
# # with Session(engine) as session:
# #     item1 = LineItem(invoice_id=invoice.id, item_name="Paper", amount=500.0)
# #     item2 = LineItem(invoice_id=invoice.id, item_name="Pens", amount=200.0)
# #     item3 = LineItem(invoice_id=invoice.id, item_name="Stapler", amount=150.0)
# #     session.add(item1)
# #     session.add(item2)
# #     session.add(item3)
# #     session.commit()

# # print(f"Created invoice {invoice.id} with line items")


# # def filter_by_amount(invoice_id:int,amount:float):
# #     with Session(engine) as session:
# #         statment= select(LineItem).where(and_(LineItem.invoice_id==invoice_id, LineItem.amount>= amount))
# #         filterd_data=session.exec(statment).all()
# #         for item in filterd_data:
# #             print(item)

# def join_invoices():
#     with Session(engine) as session:
#         statement = select(Invoice,LineItem).join(LineItem,Invoice.id ==  LineItem.invoice_id)
#         result = session.exec(statement).all()
#         for invoice ,item in result:
#             print(f"{invoice.vendor_name} - {item.item_name}: {item.amount}")


# def left_join():
#     with Session(engine) as session:
#         statement= select(Invoice,LineItem).join(LineItem,LineItem.invoice_id==Invoice.id, isouter=True)
#         result = session.exec(statement).all()
#         for invoice , item in result:
#             print(f"{invoice.vendor_name} - {item.item_name}: {item.amount}")
            
# # filter_by_amount(invoice_id=3, amount=400)
# join_invoices()
# print("\n")
# left_join()

from sqlmodel import Session, select
from app.database import engine
from app.models import Invoice, LineItem

from sqlmodel import Session, select

# 1. Inner Join (Only Invoices with Line Items)
print("=" * 95)
print(f"{'INNER JOIN: Invoices with Line Items':^65}")
print("=" * 95)
print(f"{'Vendor Name':<25} | {'Item Name':<25} | {'Amount':>8}")
print("-" * 95)

with Session(engine) as session:
    statement = select(Invoice, LineItem).join(LineItem, Invoice.id == LineItem.invoice_id)
    results = session.exec(statement).all()
    
    for invoice, item in results:
        print(f"{invoice.vendor_name:<25} | {item.item_name:<25} | {item.amount:>8.2f}")

print("\n\n")

# 2. Left Outer Join (Includes Invoices without Line Items)
print("=" * 95)
print(f"{'LEFT OUTER JOIN: All Invoices (Including Empty)':^65}")
print("=" * 95)
print(f"{'Vendor Name':<25} | {'Item Name':<25} | {'Amount':>8}")
print("-" * 95)

with Session(engine) as session:
    statement = select(Invoice, LineItem).join(LineItem, Invoice.id == LineItem.invoice_id, isouter=True)
    results = session.exec(statement).all()
    
    for invoice, item in results:
        item_name = item.item_name if item else "N/A (No Items)"
        item_amount = f"{item.amount:>8.2f}" if item else f"{'0.00':>8}"
        
        print(f"{invoice.vendor_name:<25} | {item_name:<25} | {item_amount}")

print("=" * 95)