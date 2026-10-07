import os
_raw_db_url = os.getenv("DATABASE_URL", "sqlite:///soulsync.db")
if _raw_db_url and not _raw_db_url.startswith(("sqlite://", "postgresql://", "postgres://")):
    DATABASE_URL = "sqlite:///soulsync.db"
else:
    DATABASE_URL = _raw_db_url
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL_ID = os.getenv("GEMINI_MODEL_ID", "gemini-2.0-flash")

def get_diagnostics():
    return {
        "Database": "SQLite" if "sqlite" in DATABASE_URL else "PostgreSQL",
        "Google API Key": "Configured" if GOOGLE_API_KEY else "Missing (Fallback Mode)",
        "Model": GEMINI_MODEL_ID,
    }
