# Progress Log — Invoice Parser

## Day 1 — Aug 30, 2026

### What I Did
Set up the project, installed all dependencies, created a virtual environment, and connected Python to PostgreSQL using SQLAlchemy (via SQLModel).

**Files created:**
- `database.py`
- `models.py`
- `create_tables.py`
- `insert_invoice.py`
- `query_invoice.py`
- `test_connection.py`

### What I Learned

**1. Connecting to the database (`database.py`)**
To connect to a database, you first need to create an `engine`. I created `database.py` and built the engine by providing a database URL, which includes:
- The database type (`postgresql`)
- Username and password (`postgres` / `admin123`)
- Host (`localhost`) and port (`5432`)
- Database name (`invoicedb`)

The engine manages a pool of reusable connections — opening a connection is slow (handshake + authentication), so the engine reuses connections instead of opening a new one every time.

**2. Defining the table shape (`models.py`)**
I created a model to define how my `Invoice` table should look, using SQLModel:
- `id: Optional[int]` with `primary_key=True, default=None` — the `id` must be allowed to be `None` in Python because PostgreSQL auto-generates the real id when the row is actually saved. We don't assign it ourselves.
- `vendor_name: str`, `amount: float`, `date: str` — the other columns, each with their proper type.

**3. Creating the actual table (`create_tables.py`)**
After defining the model, the table only exists in Python — not yet in the database. To actually create it, I run:
```python
SQLModel.metadata.create_all(engine)
```
`SQLModel.metadata` is a registry that keeps track of every class defined with `table=True`. When `create_all(engine)` runs, it goes through that registry and creates the real tables in PostgreSQL for anything that doesn't exist yet.

**4. Inserting data (`insert_invoice.py`)**
To insert a row, I need the `engine`, a `session`, and my table (model class).

```python
with Session(engine) as session:
    invoice = Invoice(vendor_name="...", amount=..., date="...")
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
```

- `Session(engine)` creates a new session, which borrows a connection from the engine's pool to do its work.
- `session.add(invoice)` stages the data — it is NOT in the database yet.
- `session.commit()` actually pushes the data into the database.
- `session.refresh(invoice)` reloads the object from the database — this matters because the `id` didn't exist in Python's memory until PostgreSQL generated it during commit. Refresh runs a `SELECT` behind the scenes to pull the real saved row (including the new `id`) back into my Python variable.

**5. The `with` statement**
Using `with Session(engine) as session:` means the session is automatically closed when the block finishes — even if something goes wrong inside it. I don't have to manually remember to close/release it.

**6. `echo=True`**
In `database.py`, I set `echo=True` on the engine. This makes SQLAlchemy print out every SQL command it runs behind the scenes — useful for learning/debugging, since I can see exactly what SQL my Python code is generating. In production, this is usually turned off (`echo=False`).

### Corrections / Notes to Self
- Sessions are NOT pooled and reused — only **connections** are pooled by the engine. A new `Session` object is created fresh each time.
- `create_all()` only creates tables that don't already exist — it does NOT update existing tables if the model changes later. If I change a column, I need to drop and recreate the table (or use a migration tool like Alembic, later in the roadmap).
- Library underneath SQLModel is called **SQLAlchemy**.

### Deliverables Confirmed
- ✅ Connection test prints "connected" with no errors
- ✅ `invoice` table exists in PostgreSQL with correct columns (verified via `\d invoice`)
- ✅ Row inserted, confirmed directly in psql (`SELECT * FROM invoice;`)
- ✅ Row queried back successfully from Python script