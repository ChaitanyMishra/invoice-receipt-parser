# Invoice Parser

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?logo=celery&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)

**Live Demo:** https://invoice-web-hw3q.onrender.com
*(Hosted on a free tier. The first request after inactivity can take 30–60 seconds while the service wakes up.)*

A backend service that turns uploaded invoices and receipts into structured data.

It uses **multi-pattern regex** for speed and zero cost, **validates** the output, and falls back to **LLMs (Groq → Gemini)** only for the fields regex cannot reliably extract. Batch uploads are processed asynchronously with **Celery + Redis**. If every LLM provider fails, the pipeline still returns the regex results instead of crashing.

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
- **Text extraction:** native text extraction from PDFs using `pdfplumber`.
- **Multi-pattern regex parsing:** instant extraction of 6 standard fields with high accuracy on structured GST invoices.
- **Validation layer:** enforces format constraints and cross-field rules to catch regex false positives.
- **Hybrid parsing engine:** regex first (fast, zero cost); LLMs are invoked only for complex or missing fields.
- **Multi-provider LLM fallback:** Groq is the primary provider, with automatic fallback to Gemini on rate limits or errors.
- **Async batch processing:** background processing through Celery workers and Redis.
- **Retry logic:** exponential backoff for transient errors.
- **Idempotent writes:** re-parsing updates the existing invoice record instead of creating duplicates.
- **Graceful degradation:** falls back to partial regex results if all LLM providers are unavailable.
- **JWT authentication:** secure login with strict per-user data isolation.
- **Excel export:** export parsed invoices to `.xlsx` using `openpyxl`.
- **Database migrations:** schema changes managed with Alembic.
- **Automated tests:** Pytest suite covering authentication, file handling, and security boundaries.
- **Structured logging:** standard Python logging configured for terminal output.
- **Basic frontend:** simple UI for uploading files, managing auth, and viewing extraction status.
- **Interactive API docs:** auto-generated Swagger UI at `/docs`.

---

## How It Works

### Single-File Pipeline

```mermaid
flowchart TD
    A["Client uploads file<br/>POST /files"] --> B["Save to disk + UploadedFile row"]
    B --> C["POST /files/{id}/extract<br/>pdfplumber → extracted_text"]
    C --> D["POST /files/{id}/parse<br/>Regex extraction (6 fields)"]
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

### Async Batch Flow

```mermaid
flowchart TD
    A["Client uploads many files<br/>POST /batch-upload"] --> B["Create Batch row<br/>total_files = N, status = pending"]
    B --> C["For each file:<br/>save to disk + UploadedFile row"]
    C --> D["Queue Celery task per file<br/>process_file.delay(file_id)"]
    D --> E["Return batch_id + total_files<br/>immediately"]
    D --> R[("Redis queue")]
    R --> W["Celery worker (separate process)<br/>picks up task"]
    W --> X["Extract text → parse → save Invoice + LineItems"]
    X --> Y["Update UploadedFile.status"]
    Y --> Z["Increment Batch.completed_files / failed_files<br/>recompute Batch.status when all done"]
```

---

## Field Extraction Strategy

| Field | Strategy | Notes |
|---|---|---|
| `invoice_number` | Regex | Multi-pattern, first match wins |
| `date` | Regex | Multi-format date parsing |
| `gstin` | Regex | Validated against Indian GSTIN format rules |
| `order_number` | Regex | Matched via Reference / Order labels |
| `total` | Regex | Multi-pattern match for invoice total |
| `tax_amount` | Regex | Extracted from IGST / CGST / SGST breakdowns |
| `vendor_name` | LLM only | Complex, unstructured field |
| `address` | LLM only | Complex, unstructured field |
| `line_items` | LLM only | Multi-line table structure extraction |

**Regex-only parse time:** ~0.001 s per invoice.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Framework | FastAPI |
| ORM | SQLModel (SQLAlchemy + Pydantic) |
| Database | PostgreSQL (Alembic migrations) |
| PDF extraction | pdfplumber |
| Async queue | Celery 5.6 |
| Broker | Redis |
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

The repository includes a `Dockerfile` and `docker-compose.yml`. From the project root:

```bash
docker compose up --build
```

Make sure your `.env` file exists first. Check `docker-compose.yml` for the services and ports it exposes.

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
| `REDIS_URL` | Redis URL used as the Celery broker |
| `GROQ_API_KEY` | Primary LLM provider key |
| `GEMINI_API_KEY` | Fallback LLM provider key |
| `SECRET_KEY` | Secret used to sign JWT tokens |

> ⚠️ Never commit your `.env` file. Make sure it is listed in `.gitignore`.

---

## API Reference

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/register` | Register a new user account | No |
| `POST` | `/login` | Authenticate and get a JWT access token | No |
| `GET` | `/health` | Health check | No |
| `GET` | `/` | Web user interface | No |
| `POST` | `/files` | Upload a single file (PDF / JPG / PNG) | Yes |
| `POST` | `/batch-upload` | Upload multiple files for async processing | Yes |
| `GET` | `/get_upload_data` | List all files uploaded by the authenticated user | Yes |
| `GET` | `/files/{id}` | Get metadata for a specific uploaded file | Yes |
| `POST` | `/files/{id}/extract` | Extract raw text from an uploaded file (PDF) | Yes |
| `POST` | `/files/{id}/parse` | Parse extracted text into a structured Invoice record | Yes |
| `DELETE` | `/files/{id}` | Delete the file from disk and its database record | Yes |
| `GET` | `/invoices/export` | Download parsed invoice data as an Excel file | Yes |

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

**4. Export everything to Excel**

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
│   └── test_main.py
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

- **Regex-first processing:** pattern matching runs in about 1 ms at zero API cost. High-confidence labeled fields (invoice number, date, GSTIN, totals) are resolved with regex, and LLMs are reserved for complex structures such as vendor details and line items.
- **Validation engine:** regex output is checked against strict type rules and cross-field logic (for example, `tax_amount <= total`) to remove false positives before any LLM fallback.
- **Hierarchical LLM fallback:** Groq is the fast primary provider. On HTTP 429 (rate limit) or 503 errors, execution moves to Gemini. If both fail, regex results are kept.
- **Asynchronous task queue:** batch uploads are handed to Celery workers through Redis, and the API returns a `batch_id` immediately so request threads are never blocked.
- **Multi-tenant security model:** file access, invoice reads, exports, and deletes are all scoped to the authenticated `user_id`.
- **Idempotent writes:** re-parsing a file updates the existing invoice, so retries and re-runs never create duplicates.

---

## Testing

```bash
pytest tests/test_main.py -v
```

The suite covers authentication, file handling, and security boundaries (for example, one user cannot access another user's files).

---

## Known Limitations

- **Scope:** optimized for Indian GST invoice formats. Non-GST or international receipts rely on best-effort LLM processing.
- **PDF type:** supports text-native PDFs only. Scanned or image-based PDFs need an OCR step (planned).
- **One invoice per file:** each uploaded document is expected to contain a single logical invoice.
- **LLM rate limits:** large batches can slow down when free-tier LLM rate limits are reached.

---

## Roadmap

- [x] File upload pipeline (single and batch)
- [x] PDF native text extraction (pdfplumber)
- [x] Multi-pattern regex parsing engine
- [x] Validation layer (formats and cross-field constraints)
- [x] LLM fallback orchestrator (Groq → Gemini)
- [x] Line-item table parsing
- [x] Celery + Redis background worker
- [x] Idempotent database writes and transactions
- [x] JWT authentication and per-user data isolation
- [x] Excel export (openpyxl)
- [x] Database migrations (Alembic)
- [x] Test suite
- [ ] Multi-invoice PDF splitting

---

## Author

**Chaitany Mishra**

[GitHub](https://github.com/ChaitanyMishra) · [LinkedIn](https://www.linkedin.com/in/chaitanymishra/)
