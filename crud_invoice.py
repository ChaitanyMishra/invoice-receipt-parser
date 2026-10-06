from sqlmodel import SQLModel,select,Session
from app.database import engine
from typing import Optional
from app.models import LineItem , Invoice
import datetime

def create_invoice(parsed_data:dict, uploaded_file_id:int):
    with Session(engine) as session:
        date=parsed_data.get('date')
        parsed_date= datetime.datetime.strptime(date,"%d.%m.%Y").date()
        total_amount = float(parsed_data.get('total'))
        total_tax = float(parsed_data.get('tax_amount'))
        sub_total = float(total_amount-total_tax)
        invoice = Invoice(
                total=float(parsed_data.get('total')) if parsed_data.get('total') else None,
                tax_amount=parsed_data.get('tax_amount') if parsed_data.get('tax_amount') else None,
                order_number=parsed_data.get('order_number'),
                invoice_number = parsed_data.get('invoice_number'),
                date= parsed_date,
                address=parsed_data.get('address') if parsed_data.get('address') else None,
                gstin=parsed_data.get('gstin'),
                uploaded_file_id=uploaded_file_id,
                vendor_name= parsed_data.get('vendor_name') if parsed_data.get('vendor_name') else None,
                status='completed',
                subtotal=sub_total           
                )
            
        


        session.add(invoice)
        session.commit()
        session.refresh(invoice)

        # for item in items:
        #     line_item=LineItem(invoice_id=invoice.id,item_name=item["item_name"],amount=item["amount"])
        #     session.add(line_item)
        # session.commit()
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
    test_parsed = {
        "invoice_number": "TEST-001",
        "date": "28.12.2025",
        "gstin": "29AAICA3918J1ZE",
        "order_number": "406-0000000-0000000",
        "total": "100.50",
    }
    result = create_invoice(test_parsed, uploaded_file_id=1)
    print(f"id={result.id}, number={result.invoice_number}, total={result.total}, date={result.date}, gstin={result.gstin}")
    