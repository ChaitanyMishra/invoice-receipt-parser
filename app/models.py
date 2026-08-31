from sqlmodel import SQLModel , Field
from typing import Optional

class Invoice(SQLModel, table=True):
    id:Optional[int]= Field(primary_key=True, default=None)
    vendor_name:str
    amount:float
    date:str


class LineItem(SQLModel,table=True):
    id:Optional[int]=Field(primary_key=True, default=None)
    invoice_id:int=Field(foreign_key="invoice.id")
    item_name:str
    amount:float