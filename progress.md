# Progress Log — Invoice Parser

Day 1 — Aug 30
Built: PostgreSQL connection (engine), Invoice model, table creation, insert, and query — full basic CRUD loop working end to end
Files: database.py, models.py, create_tables.py, insert_invoice.py, query_invoice.py, test_connection.py
Status: Done ✅ — connection tested, table verified in psql, row inserted and queried successfully

Day 2 — Sep 01
LineItem model with foreign key to Invoice (one-to-many relationship), normalization reasoning understood, insert flow (Invoice → refresh → LineItems → commit), query with select().where(), moved DB credentials to .env, GitHub repo created and pushed (invoice-receipt-parser)

Day 3 — Sep 04
Built: CRUD operation for Database(Create Invoice , Delete Invoice, Update Invoice, Retrive Invoice)
Files: worked on crud_invoice.py
Learn: 
    1- How to delete Data in DB if it reffer in other tables Like Forign key
    2- Use of Flush() - session.fush()
    3- diffrence between commit() and flush()
    
Day 4 - Sep 06
Buit: multi-condition filtering, defensive existence checks, __name__ guard
Files: test_model.py
Learn: 
1-   How to add Mutliple filtering using and_() 
2-   Why we need and_() when sqlModel allow mutliple conditito seprated by , 
3-   importence of __main__ == __main__


Day 5 - Sep  11
Built: 




