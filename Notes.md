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



Day 02 -


Day 03 - TOday i write code for CRUD operations in DB how user invoice Create in DB and Delete in DB and Update in DB and Retrive from DB in which i use to write Functions-

get_invoice(invoice_id:int): - here seimply open a session get session from engine and use sql model command sesson.get(Invoice , invoice_id) it take invoice id from user search in DB and fetch the data 

create_invoice- it take inoout from use like vendor name , date , amount and useing sql model command session.add and adddetails then commit and refresh it

update_invoice - here what i learn is here we take input from use also like name , amount,date but we set default value as  None becase if we not set default value and user only give updated value eg - only amount so other feild automettly get deleted so to prevent that we set defaut value as None and when we update we check like if this is not none then value = updated value we dont need any kind of .uodate in sql model just like other .add, .delete because sqlmodel alredy under the hood identify when we retrive data sql model set in session and trak all changes we dont add new thing we just update so it marked updated data as dirty and execute sql.update command and update old data not creating new 

delete_invoice -  here we take delted id as inout and run session.delete command but if your data table is reffer to other table or have relationship like 1  to many or many to one  postgres  prevent to delete data directly so we have 2 option 1st - automettly cascading where we write code in database layer that if we execute any delete qurry it also delte in other tables but it is resky and delete your data permanetly but if u want full controle we can write manully in delte querry 1st we 1st run the querry for another table where our data is store here Line item table we run querry like - Select(LineItem).where(Line_item.invoice_id==invoice_id) to get all releted data then execute comand using session.exec(statment).all nown we have data now run the loop and delete item in lineItem then we use Flush() to stage out changes then we delte our main table data like session.delete(invoice)

The Error i counter with is - 
 psycopg2.errors.ForeignKeyViolation - because we try to delte invoce 1st without delting related data in lineitem 

 psycopg2.errors.ForeignKeyViolation- even though my code was correct i see this because internaly SQLAlchemy/SQLModel delays and reorders SQL statements inside a session to optimize performance. so we use Flush() to fix the error 

commit() - does TWO things: sends all staged changes to the DB (flush) AND finalizes/closes the transaction, making changes permanent

flush() - does ONE thing: sends staged changes to the DB, but the transaction stays OPEN — nothing is finalized yet, could still be rolled back

flush() - it do only one thing is stage the changes in a queue 