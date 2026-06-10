import os

# Get DATABASE_URL, but validate it; fallback to SQLite if invalid
_raw_db_url = os.getenv("DATABASE_URL", "sqlite:///soulsync.db")

# If DATABASE_URL looks malformed, use SQLite instead
if _raw_db_url and not _raw_db_url.startswith(("sqlite://", "postgresql://", "postgres://")):
    print(f"⚠️ Invalid DATABASE_URL detected. Using SQLite fallback.")
    DATABASE_URL = "sqlite:///soulsync.db"
else:
    DATABASE_URL = _raw_db_url

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL_ID = os.getenv("GEMINI_MODEL_ID", "gemini-2.0-flash")

def get_diagnostics():
    return {
        "Database": "SQLite (Default)" if "sqlite" in DATABASE_URL else "Postgres",
        "Google API Key": "Configured" if GOOGLE_API_KEY else "Missing (Fallback Mode)",
        "Model": GEMINI_MODEL_ID
    }


# ============================================================
# NIMS - Neurodivergent Interaction Modelling System
# ============================================================

NIMS_ENABLED = os.getenv("NIMS_ENABLED", "true").lower() == "true"

NIMS_REQUIRE_APPROVED_MODEL = (
    os.getenv("NIMS_REQUIRE_APPROVED_MODEL", "true").lower() == "true"
)

NIMS_DEBUG_PANEL = os.getenv("NIMS_DEBUG_PANEL", "false").lower() == "true"

NIMS_DEFAULT_PROVIDER = os.getenv("NIMS_DEFAULT_PROVIDER", "gemini")
NIMS_DEFAULT_MODEL_ID = os.getenv("NIMS_DEFAULT_MODEL_ID", "gemini-default")

NIMS_MIN_APPROVAL_SCORE = float(os.getenv("NIMS_MIN_APPROVAL_SCORE", "0.82"))

NIMS_MAX_SAFETY_FAILURES = int(os.getenv("NIMS_MAX_SAFETY_FAILURES", "0"))
NIMS_MAX_TOPIC_FAILURES = int(os.getenv("NIMS_MAX_TOPIC_FAILURES", "1"))
NIMS_MAX_LITERALNESS_FAILURES = int(os.getenv("NIMS_MAX_LITERALNESS_FAILURES", "1"))
