from sqlmodel import Session
from app.models import Invoice
from app.database import engine

with Session(engine) as session:
    result = session.get(Invoice , 2)
    print(result)