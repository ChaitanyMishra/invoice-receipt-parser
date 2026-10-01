from sqlmodel import SQLModel , Field
from typing import Optional
import datetime

class Invoice(SQLModel, table=True):
    # db info
    id:Optional[int]= Field(primary_key=True, default=None)
    uploaded_file_id:Optional[int]=Field(foreign_key="uploadedfile.id",default=None)
    status:str=Field(default="pending")
    created_at:datetime.datetime=Field(default_factory=datetime.datetime.now)

    # vendor info
    vendor_name:Optional[str]=Field(default=None,max_length=150)
    gstin:Optional[str]=Field(default=None)
    address:Optional[str]=Field(default=None)

    # Total
    total:Optional[float]=Field(default=None)
    subtotal:Optional[float]=Field(default=None)
    tax_amount:Optional[float]=Field(default=None)

    # invoice info
    invoice_number:Optional[str]=Field(default=None)
    date:Optional[datetime.date]=Field(default=None)
    order_number:Optional[str]=Field(default=None)



class LineItem(SQLModel,table=True):
    # db info
    id:Optional[int]=Field(primary_key=True, default=None)
    invoice_id:int=Field(foreign_key="invoice.id")

    # item info
    item_name:str
    amount:float
    description:Optional[str]=Field(None)
    unit_price:Optional[float]=Field(default=None)
    quantity:Optional[float]=Field(default=None)

class UploadedFile(SQLModel, table=True):
    id:Optional[int]=Field(primary_key=True,default=None)
    filename:str
    size:int
    filepath:str
    uploaded_at:datetime.datetime=Field(default_factory=datetime.datetime.now)
    extracted_text:Optional[str]=Field(default=None)