from sqlmodel import Session, select
from app.models import LineItem
from app.database import engine

with Session(engine) as session:
    statment = select(LineItem).where(LineItem.invoice_id==1)
    result = session.exec(statment).all()

    for item in result:
        print(item)
