from sqlmodel import SQLModel
from app.database import engine
from app.models import Invoice, LineItem

SQLModel.metadata.create_all(bind=engine, )