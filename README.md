# Invoice Parser API

A backend service that extracts structured data from uploaded invoices and receipts. Combines **regex** for speed and **LLMs** (Gemini + Groq) for fields that regex can't extract, with graceful fallback across providers.

## Features

- 📤 Upload invoices (PDF, JPG, PNG)
- 📝 Extract text from text-based PDFs using `pdfplumber`
- 🔍 Parse structured fields using **regex** (fast, free)
- 🤖 **LLM fallback** for missing fields (Gemini → Groq)
- 💾 Store parsed invoices in PostgreSQL
- 🔁 Idempotent save (re-parsing updates, doesn't duplicate)
- ⚠️ Graceful degradation (LLM failure doesn't crash the pipeline)

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Framework | FastAPI |
| ORM | SQLModel (SQLAlchemy + Pydantic) |
| Database | PostgreSQL |
| PDF Parsing | pdfplumber |
| LLM Providers | Google Gemini 2.5 Flash, Groq (openai/gpt-oss-120b) |
| Config | python-dotenv |

## Architecture
User uploads file
↓
POST /files → save to disk + UploadedFile row in DB
↓
POST /files/{id}/extract → pdfplumber → extracted_text saved to DB
↓
POST /files/{id}/parse
↓
┌─────────────────────────────────────┐
│ 1. Regex extraction (fast, free) │ → invoice_number, date, gstin,
│ │ order_number, total, tax_amount
└─────────────────────────────────────┘
↓
Check: any fields still None?
↓ ↓
YES NO
↓ ↓
┌───────────────────────┐ │
│ 2. LLM Fallback │ │
│ a. Try Gemini │ │
│ b. If fail → Groq │ │
│ → vendor_name │ │
│ → address │ │
└───────────────────────┘ │
↓ ↓
└─────────┬──────────┘
↓

Save/update Invoice row in DB
↓

Return complete parsed data


## Project Structure

├── app/
│ ├── init.py
│ ├── database.py # SQLModel engine + .env loading
│ ├── models.py # UploadedFile, Invoice, LineItem models
│ ├── main.py # FastAPI routes
│ └── services/
│ ├── init.py
│ ├── pdf_extractor.py # extract_text_from_pdf()
│ ├── invoice_parser.py # parse_invoice_text() — regex + LLM orchestration
│ └── llm_extractor.py # Gemini + Groq wrappers
├── uploads/ # Uploaded files (gitignored)
├── venv/
├── .env # DB_URL, GEMINI_API_KEY, GROQ_API_KEY (gitignored)
├── .gitignore
├── create_tables.py # Create DB tables
├── drop.py # Drop all DB tables
├── crud_invoice.py # Invoice CRUD operations
├── crud_uploaded_file.py # UploadedFile CRUD operations
├── requirements.txt
└── README.md


## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check / welcome message |
| `POST` | `/files` | Upload a file (PDF/JPG/PNG) |
| `GET` | `/files` | List all uploaded files |
| `GET` | `/files/{id}` | Get one uploaded file's metadata |
| `POST` | `/files/{id}/extract` | Extract text from the file (PDF only) |
| `POST` | `/files/{id}/parse` | Parse text → create/update Invoice row |
| `DELETE` | `/files/{id}` | Delete file from disk + DB |

## Database Schema

**`uploadedfile`**
| Column | Type | Notes |
|---|---|---|
| id | int | PK |
| filename | str | Original filename |
| size | int | Bytes |
| filepath | str | Path on disk |
| uploaded_at | datetime | Auto-set |
| extracted_text | str (nullable) | Filled by `/extract` |

**`invoice`**
| Column | Type | Notes |
|---|---|---|
| id | int | PK |
| uploaded_file_id | int (FK, nullable) | Links to uploadedfile |
| status | str | pending / processing / completed / failed |
| created_at | datetime | Auto-set |
| vendor_name | str (nullable) | Extracted via LLM fallback |
| gstin | str (nullable) | Vendor GST number |
| address | str (nullable) | Vendor address |
| subtotal | float (nullable) | Computed = total - tax |
| tax_amount | float (nullable) | Total tax |
| total | float (nullable) | Grand total |
| invoice_number | str (nullable) | Vendor's invoice number |
| date | date (nullable) | Invoice date |
| order_number | str (nullable) | Order reference |

**`lineitem`**
| Column | Type | Notes |
|---|---|---|
| id | int | PK |
| invoice_id | int (FK) | Links to invoice |
| item_name | str | Item description |
| amount | float | Line amount |
| description | str (nullable) | |
| unit_price | float (nullable) | |
| quantity | float (nullable) | |

## Setup

### 1. Clone and install

```bash
git clone https://github.com/ChaitanyMishra/invoice-receipt-parser
cd invoice-receipt-parser
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

2. Configure environment
Create a .env file at the project root:
DB_URL=postgresql://user:password@localhost:5432/invoicedb
GEMINI_API_KEY=your_gemini_key_here
GROQ_API_KEY=your_groq_key_here

Gemini API key: Get from aistudio.google.com (free tier: 20 requests/day)
Groq API key: Get from console.groq.com (free tier: 1000 requests/day)

3. Create database tables
python create_tables.py

4. Run the server
uvicorn app.main:app --reload

Usage Example
# 1. Upload an invoice
curl -X POST http://127.0.0.1:8000/files \
  -F "file=@invoice.pdf"
# → {"id": 1, "filename": "invoice.pdf", "size": 92433}

# 2. Extract text
curl -X POST http://127.0.0.1:8000/files/1/extract
# → {"status": "extracted", "length": 3445, "preview": "..."}

# 3. Parse
curl -X POST http://127.0.0.1:8000/files/1/parse
# → {
#     "status": "parsed",
#     "invoice_id": 1,
#     "parsed_data": {
#       "invoice_number": "POD-26-241475108",
#       "date": "28.12.2025",
#       "gstin": "29AAICA3918J1ZE",
#       "order_number": "406-6548532-6482720",
#       "total": "7.00",
#       "tax_amount": "1.07",
#       "vendor_name": "Amazon Seller Services Private Limited",
#       "address": "#26/1, Brigade Gateway, ..."
#     }
#   }

Design Decisions
Why regex first, then LLM?
Regex is fast (~1ms) and free. LLM calls take 3-9 seconds and cost money. For invoices with standard labels (Invoice Number: ..., TOTAL: ...), regex extracts everything. We only call the LLM when fields are missing — saving cost and latency.

Why two LLM providers?
Gemini's free tier: 20 requests/day. Too restrictive for real testing.
Groq's free tier: 1000 requests/day.
Both use the same prompt structure. If Gemini is rate-limited (429) or down (503), the pipeline falls back to Groq. If both fail, we return regex-only data — never crash.

Why idempotent save?
Calling /parse twice used to create two Invoice rows. Now it checks for an existing Invoice by uploaded_file_id and updates it if it exists. Same endpoint can be called repeatedly without side effects.

Why separate /extract and /parse?
/extract = file → text (fast, no LLM)

/parse = text → structured data (may call LLM)

Separating them means:

Re-parsing doesn't require re-extracting

Extraction can be cached

Failures are isolated to one stage

Known Limitations
Text-based PDFs only for now. Scanned PDFs and images need OCR (Tesseract) — planned.

Regex covers Amazon/Clicktech format primarily. Other vendors' invoices rely on the LLM fallback.

No authentication yet. All endpoints are open — JWT auth planned.

No line item extraction yet. Coming next.

Roadmap
☑ File upload + metadata storage
☑ PDF text extraction (pdfplumber)
☑ Regex-based field extraction
☑ LLM fallback (Gemini + Groq)
☑ Idempotent DB save
□ Line item extraction from tables
□ JWT authentication
□ Docker + deployment (Render/Railway)
□ OCR for scanned PDFs (Tesseract)
□ Tests (pytest)
Author
Chaitany Mishra — GitHub · LinkedIn
