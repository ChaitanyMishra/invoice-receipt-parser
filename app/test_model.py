from sqlmodel import SQLModel,Field
from typing import Optional


class Customer(SQLModel, table=True):
    id:Optional[int]=Field(default=None,primary_key=True)
    name:str
    email:str

class Order(SQLModel,table=True):
    id:Optional[int]=Field(default=None,primary_key=True)
    customer_id:int=Field(foreign_key="customer.id")
    product_name:str
    price:str
