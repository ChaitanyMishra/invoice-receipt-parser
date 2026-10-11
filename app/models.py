import datetime

from sqlmodel import Field, SQLModel


class Invoice(SQLModel, table=True):
    # db info
    id: int | None = Field(primary_key=True, default=None)
    uploaded_file_id: int | None = Field(foreign_key="uploadedfile.id", default=None)
    status: str = Field(default="pending")
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)

    # vendor info
    vendor_name: str | None = Field(default=None, max_length=150)
    gstin: str | None = Field(default=None)
    address: str | None = Field(default=None)

    # Total
    total: float | None = Field(default=None)
    subtotal: float | None = Field(default=None)
    tax_amount: float | None = Field(default=None)

    # invoice info
    invoice_number: str | None = Field(default=None)
    date: datetime.date | None = Field(default=None)
    order_number: str | None = Field(default=None)


class LineItem(SQLModel, table=True):
    # db info
    id: int | None = Field(primary_key=True, default=None)
    invoice_id: int = Field(foreign_key="invoice.id")

    # item info
    item_name: str
    amount: float
    description: str | None = Field(None)
    unit_price: float | None = Field(default=None)
    quantity: float | None = Field(default=None)


class UploadedFile(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)
    filename: str
    size: int
    filepath: str
    uploaded_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    extracted_text: str | None = Field(default=None)
