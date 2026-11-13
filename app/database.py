import os
import sys

from dotenv import load_dotenv
from sqlmodel import create_engine

load_dotenv()


def get_database_url():
    if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("TESTING") == "1":
        return "sqlite:///./test_invoice_parser.db"

    if "pytest" in " ".join(sys.argv).lower():
        return "sqlite:///./test_invoice_parser.db"

    db_url = os.getenv("DB_URL")
    if db_url:
        return db_url

    raise RuntimeError(
        "DB_URL must be set for non-test environments. SQLite is only allowed in testing/dev flows."
    )


DB_URL = get_database_url()
engine = create_engine(DB_URL, echo=False, pool_pre_ping=True)
