# Invoice Parser API

**Live Demo:** https://invoice-web-hw3q.onrender.com
*(Hosted on a free tier. The first request after inactivity can take 30–60 seconds while the service wakes up.)*

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?logo=celery&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)

A backend service that turns uploaded invoices and receipts into structured data.

It uses **labeled-text regex** first for speed and zero cost, **validates** monetary values and arithmetic, and calls **LLMs (Groq → Gemini)** only for fields that need contextual extraction. Multi-file uploads stay *pending* until parsing is requested, and the API limits parsing to three files per minute. If every LLM provider fails, the pipeline still returns the regex results instead of crashing.

---

## Table of Contents

- [Features](#features)
- [How It Works](#how-it-works)
- [Field Extraction Strategy](#field-extraction-strategy)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Running with Docker](#running-with-docker)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Usage Example](#usage-example)
- [Database Schema](#database-schema)
- [Project Structure](#project-structure)
- [Design Decisions](#design-decisions)
- [Testing](#testing)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)
- [Author](#author)

---

## Features

- **Indian GST focus:** optimized for Indian GST invoices (GSTIN, tax extraction), with best-effort fallback for other formats.
- **File upload:** PDF, JPG, and PNG support (single or batch), with metadata stored in PostgreSQL.
- **Text extraction:** native text extraction from text-based PDFs using `pdfplumber`.
- **Regex-first parsing:** multi-pattern extraction of 7 standard fields, with normalized money values.
- **Validation layer:** checks amount formats, line arithmetic, and subtotal/tax/total consistency; suspect invoices are marked for manual review.
- **Hybrid parsing engine:** regex first (fast, free); LLMs are invoked only for missing or context-dependent fields.
- **Multi-provider LLM fallback:** Groq is the primary provider, with automatic fallback to Gemini on rate limits or errors.
- **On-demand parsing:** batch uploads stay pending until you request parsing; parsing is limited to three files per minute across the app.
- **Background task infrastructure:** Celery workers and Redis.
- **Retry logic:** exponential backoff for transient errors.
- **Idempotent writes:** re-parsing updates the existing invoice record instead of creating duplicates.
- **Graceful degradation:** an LLM failure never breaks the pipeline; partial regex results are kept.
- **JWT authentication:** secure login with strict per-user data isolation.
- **Excel export:** export parsed invoices to `.xlsx` using `openpyxl`.
- **Database migrations:** schema changes managed with Alembic.
- **Automated tests:** Pytest suite covering authentication, file handling, security boundaries, and parser validation.
- **Structured logging:** standard Python logging configured for terminal output.
- **Frontend workspace:** separate file and invoice lists, visible status badges, and contact details.
- **Interactive API docs:** auto-generated Swagger UI at `/docs`.

---

## How It Works

### Single-File Pipeline

```mermaid
flowchart TD
    A["Client uploads file<br/>POST /files"] --> B["Save to disk + UploadedFile row"]
    B --> C["POST /files/{id}/extract<br/>pdfplumber → extracted_text"]
    C --> D["POST /files/{id}/parse<br/>Regex extraction (7 fields)"]
    D --> V["Validate<br/>format + cross-field"]
    V --> E{"Any fields<br/>still missing?"}
    E -- No --> H["Create / update Invoice row"]
    E -- Yes --> F["Try Groq"]
    F -- "Success" --> H
    F -- "429 / 503" --> G["Fallback: Gemini"]
    G -- "Success" --> H
    G -- "Failure" --> I["Keep regex-only data"]
    I --> H
    H --> J["Return parsed data"]
```

### Multi-File Flow

```mermaid
flowchart TD
    A["Client uploads many files<br/>POST /batch-upload"] --> B["Save each file as pending"]
    B --> C["Return uploaded file count"]
    C --> D["User chooses Parse All Pending"]
    D --> E["Extract and parse up to 3 files per minute"]
    E --> F["Validate amount arithmetic"]
    F --> G["Mark inconsistent values for review"]
```

---

## Field Extraction Strategy

### Per-field strategy

| Field | Strategy | Notes |
|---|---|---|
| `invoice_number` | Regex | Multi-pattern, first match wins |
| `date` | Regex | Multiple formats (`parse_date` normalizes) |
| `gstin` | Regex | Via GSTIN/UIN label; validated against Indian GSTIN format rules |
| `order_number` | Regex | Order / Reference No. labels |
| `total` | Regex | Labels such as Grand Total, Total Payable, Invoice Value, or Amount Due; excludes tax-summary rows and PDF font markers |
| `tax_amount` | Regex | IGST / CGST / SGST amounts |
| `subtotal` | Regex | Taxable value / subtotal labels |
| `vendor_name` | LLM fallback | Context-dependent text |
| `address` | LLM fallback | Context-dependent text |
| `line_items` | LLM fallback | Multi-line table extraction |

### Pipeline stages

| Stage | Responsibility | Fields |
|---|---|---|
| Regex | Fast, free, deterministic | `invoice_number`, `date`, `gstin`, `order_number`, `total`, `tax_amount`, `subtotal` |
| Validation | Rejects malformed values | Amount format, arithmetic, and cross-field checks |
| LLM fallback | One combined provider request for missing details | `vendor_name`, `address`, `line_items`, and any other missing fields |
| Review status | Flagged for manual verification | Missing or inconsistent invoice amounts |

**Regex-only parse time:** ~0.001 s per invoice.

The benchmark script in `scripts/` runs regex-only by default to avoid provider latency and API usage. Pass `--with-llm` to include provider calls when measuring end-to-end parsing; this consumes API quota.

> Extracted amounts should still be checked against the source invoice. Inconsistent or unverified totals are marked for review; parsing does not guarantee tax compliance or accounting accuracy.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Framework | FastAPI |
| ORM | SQLModel (SQLAlchemy + Pydantic) |
| Database | PostgreSQL (Alembic migrations) |
| PDF extraction | pdfplumber |
| Background tasks | Celery 5.6 |
| Cache, broker and rate limits | Redis |
| LLM providers | Groq (`openai/gpt-oss-20b`), Google Gemini (`gemini-3.5-flash-lite`) |
| Excel export | openpyxl |
| Testing | Pytest + HTTPX |
| Frontend | Vanilla HTML5 / JavaScript / CSS3 |
| Configuration | python-dotenv |
| Containers | Docker, Docker Compose |
| Hosting | Render |

---

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL running locally or hosted remotely
- Redis running locally (`sudo systemctl start redis`)
- API keys for [Groq](https://console.groq.com) and [Google AI Studio](https://aistudio.google.com)

### Installation

**1. Clone the repository**

```bash
git clone https://github.com/ChaitanyMishra/invoice-receipt-parser.git
cd invoice-receipt-parser
```

**2. Create a virtual environment and install dependencies**

```bash
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**3. Configure environment variables**

Create a `.env` file in the project root (see [Environment Variables](#environment-variables)).

**4. Run database migrations**

```bash
alembic upgrade head
```

**5. Start the FastAPI app**

```bash
uvicorn app.main:app --reload
```

The app runs at http://127.0.0.1:8000 and the interactive docs at http://127.0.0.1:8000/docs.

**6. Start the Celery worker** (in a separate terminal)

```bash
celery -A app.celery_app worker --loglevel=info --concurrency=2
```

---

## Running with Docker

The repository includes a `Dockerfile` and `docker-compose.yml`. Make sure your `.env` file exists first, then run from the project root:

```bash
docker compose up --build
```

Check `docker-compose.yml` for the services and ports it exposes.

---

## Environment Variables

Create a `.env` file in the root directory:

```env
DB_URL=postgresql://user:password@localhost:5432/invoicedb
REDIS_URL=redis://localhost:6379/0
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
SECRET_KEY=your_super_secret_jwt_key
```

| Variable | Purpose |
|---|---|
| `DB_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis URL used for Celery and rate limiting |
| `GROQ_API_KEY` | Primary LLM provider key |
| `GEMINI_API_KEY` | Fallback LLM provider key |
| `SECRET_KEY` | Secret used to sign JWT tokens |

---

## API Reference

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/register` | Register a new user account | No |
| `POST` | `/login` | Authenticate and get a JWT access token | No |
| `GET` | `/health` | Health check | No |
| `GET` | `/` | Web user interface | No |
| `POST` | `/files` | Upload a single file (PDF / JPG / PNG) | Yes |
| `POST` | `/batch-upload` | Upload multiple files as pending | Yes |
| `GET` | `/get_upload_data` | List all files uploaded by the authenticated user | Yes |
| `GET` | `/files/{id}` | Get metadata for a specific uploaded file | Yes |
| `POST` | `/files/{id}/extract` | Extract raw text from an uploaded file (PDF only) | Yes |
| `POST` | `/files/{id}/parse` | Parse text and create or update the Invoice row | Yes |
| `DELETE` | `/files/{id}` | Delete the file from disk and its database record | Yes |
| `GET` | `/invoices/export` | Download parsed invoice data as an Excel file | Yes |

`/files/{id}/parse` is limited to three files per minute across all users. The UI's **Parse All Pending** button extracts and processes at most three files per click; additional files wait for a later click and rate-limit window.

Full interactive documentation is available at `/docs` (Swagger UI).

---

## Usage Example

**1. Log in and get a JWT token**

```bash
curl -X POST http://127.0.0.1:8000/login \
  -d "username=user@example.com&password=yourpassword"
```

```json
{"access_token": "eyJhb...", "token_type": "bearer"}
```

**2. Upload an invoice**

```bash
curl -X POST http://127.0.0.1:8000/files \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@sample_invoice.pdf"
```

```json
{"id": 1, "filename": "sample_invoice.pdf", "size": 92433}
```

**3. Extract text and parse fields**

```bash
curl -X POST http://127.0.0.1:8000/files/1/extract -H "Authorization: Bearer YOUR_TOKEN"
curl -X POST http://127.0.0.1:8000/files/1/parse   -H "Authorization: Bearer YOUR_TOKEN"
```

```json
{
  "status": "parsed",
  "invoice_id": 1,
  "parsed_data": {
    "invoice_number": "POD-XX-241475XXX",
    "date": "28.12.2025",
    "gstin": "29XXXXX3918X1XX",
    "order_number": "406-6548532-XXXXXXX",
    "total": "19491.53",
    "tax_amount": "3508.47",
    "vendor_name": "Amazon Seller Services Private Limited",
    "address": "#26/1, Brigade Gateway, ..."
  }
}
```

**4. Batch upload (files stay pending until you parse them)**

```bash
curl -X POST http://127.0.0.1:8000/batch-upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "files=@invoice-1.pdf" \
  -F "files=@invoice-2.pdf"
# → {"total_files": 2, "status": "uploaded"}
```

The files remain pending until you start parsing them in the frontend.

**5. Export everything to Excel**

```bash
curl -X GET http://127.0.0.1:8000/invoices/export \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o invoices.xlsx
```

---

## Database Schema

```mermaid
erDiagram
    USER ||--o{ UPLOADEDFILE : uploads
    BATCH ||--o{ UPLOADEDFILE : groups
    UPLOADEDFILE ||--o| INVOICE : produces
    INVOICE ||--o{ LINEITEM : contains

    USER {
        int id PK
        string email UK
        string hashed_password
        datetime created_at
    }
    UPLOADEDFILE {
        int id PK
        int user_id FK
        int batch_id FK
        string filename
        int size
        string filepath
        string extracted_text
        string status
        datetime uploaded_at
    }
    BATCH {
        int id PK
        int total_files
        int completed_files
        int failed_files
        string status
        datetime created_at
    }
    INVOICE {
        int id PK
        int uploaded_file_id FK
        string status
        string vendor_name
        string gstin
        string address
        string invoice_number
        string order_number
        date date
        float subtotal
        float tax_amount
        float total
        datetime created_at
    }
    LINEITEM {
        int id PK
        int invoice_id FK
        string description
        float quantity
        float unit_price
        float amount
    }
```

**Relationships**

- A `User` owns many `UploadedFile` records, and every query is scoped by `user_id`.
- A `Batch` groups many `UploadedFile` records. `batch_id` is `NULL` for single uploads.
- An `UploadedFile` produces at most one `Invoice`. Re-parsing updates the existing row.
- An `Invoice` has many `LineItem` rows.

**Status values**

| Table | Values |
|---|---|
| `UploadedFile.status` | `pending`, `processing`, `completed`, `failed` |
| `Batch.status` | `pending`, `processing`, `completed`, `partial`, `failed` |

Schema changes are managed with Alembic (`alembic upgrade head`).

---

## Project Structure

```text
.
├── app/
│   ├── __init__.py
│   ├── auth.py                # JWT creation, hashing, user validation
│   ├── celery_app.py          # Celery configuration and Redis client setup
│   ├── database.py            # Database engine setup and env handling
│   ├── main.py                # FastAPI init, routing, static mounts
│   ├── models.py              # SQLModel schemas (User, File, Invoice, LineItem)
│   ├── tasks.py               # Celery background tasks
│   └── services/
│       ├── __init__.py
│       ├── invoice_parser.py  # Regex parsing, validation, LLM fallback logic
│       ├── llm_extractor.py   # Groq and Gemini API handlers
│       └── pdf_extractor.py   # Text extraction using pdfplumber
├── frontend/                  # Static UI
│   ├── app.js
│   ├── index.html
│   └── style.css
├── migrations/                # Alembic migrations
│   ├── env.py
│   └── versions/
├── scripts/                   # Performance testing and benchmarking utilities
├── tests/                     # Integration and unit tests
│   ├── test_main.py
│   └── test_invoice_parser.py
├── uploads/                   # Local file storage (gitignored)
├── alembic.ini                # Migration configuration
├── docker-compose.yml         # Container orchestration
├── Dockerfile                 # Container image specification
├── pytest.ini                 # Pytest settings
├── requirements.txt           # Dependencies
└── README.md
```

---

## Design Decisions

### Regex first, LLM second
Pattern matching runs in about 1 ms at zero API cost. High-confidence labeled fields (invoice number, date, GSTIN, totals) are resolved with regex, and LLMs are reserved for complex structures such as vendor details and line items. Extraction accuracy depends on document text quality and invoice layout.

### Validation engine
Regex output is checked before any LLM fallback:

- **Format:** is it a number? A parseable date? A 15-character GSTIN?
- **Cross-field:** do subtotal, tax, line items, and total agree within a small rounding tolerance?

If validation fails, the invoice remains available but is marked for manual review. Arithmetic checks flag suspicious results but do not replace manual verification.

### Why Groq primary, Gemini fallback?
Groq's free tier has higher throughput (about 1,000 requests/day vs Gemini's ~500) and faster inference for the small model. Gemini is the safety net for when Groq rate-limits (429) or is unavailable (503). If both fail, the pipeline returns regex-only data rather than an error.

### Why on-demand parsing?
Uploads remain pending until requested. This prevents a large batch from immediately consuming provider quota; the API limits parse requests to three files per minute, and the UI processes them sequentially.

### Why idempotent writes?
Calling `/parse` twice used to create duplicate `Invoice` rows. The save now looks up an existing invoice by `uploaded_file_id` and updates it instead of inserting. Batch counters use atomic `UPDATE ... SET x = x + 1` to avoid race conditions across workers.

### Why separate `/extract` and `/parse`?
- `/extract` is file → text (fast, no LLM)
- `/parse` is text → structured data (may call an LLM)

Separating them means re-parsing does not require re-extracting, extracted text is cached in the database, and a failure is isolated to a single stage.

### Multi-tenant security model
File access, invoice reads, exports, and deletes are all scoped to the authenticated `user_id`.

---

## Testing

```bash
pytest
```

- `tests/test_main.py` covers authentication, file handling, and security boundaries (for example, one user cannot access another user's files).
- `tests/test_invoice_parser.py` covers parser validation cases.

---

## Known Limitations

- **Scope:** optimized for Indian GST invoice formats. Non-GST or international receipts rely on best-effort LLM processing.
- **Text-based PDFs only:** scanned PDFs and images need an OCR step (Tesseract), which is planned.
- **One invoice per file:** only the first invoice in a PDF is parsed. Splitting multi-invoice PDFs by invoice number is the next feature.
- **Vendor-specific coverage:** regex is tuned for Amazon and similar formats. Unusual vendors (e.g. `rent swap`, `WEMI`) fall back entirely to the LLM and may fail on rate limits.
- **Free-tier LLM rate limits:** parsing is capped at three files per minute, and unusual invoices may still require manual verification.

---

## Roadmap

- [x] File upload (single + batch) with metadata storage
- [x] PDF text extraction (pdfplumber)
- [x] Multi-pattern regex parsing
- [x] Validation layer (format + cross-field)
- [x] LLM fallback (Groq → Gemini)
- [x] Line-item extraction via LLM
- [x] Rate-limited on-demand parsing
- [x] Retry with exponential backoff
- [x] Idempotent writes (Invoice + batch counters)
- [x] Celery + Redis background infrastructure
- [x] JWT authentication + per-user isolation
- [x] Excel export (openpyxl)
- [x] Database migrations (Alembic)
- [x] Structured logging
- [x] Pytest test suite
- [x] Basic frontend
- [x] Docker + docker-compose
- [x] Deployment (Render)
---

## Author

**Chaitany Mishra**

[GitHub](https://github.com/ChaitanyMishra) · [LinkedIn](https://www.linkedin.com/in/chaitanymishra/)
