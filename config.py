"""Central configuration for LeakSentry. Reads from the environment (.env)."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# ---- Paths ----
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
CONTRACTS_CSV = os.path.join(DATA_DIR, "contracts.csv")
INVOICES_CSV = os.path.join(DATA_DIR, "invoices.csv")
USAGE_CSV = os.path.join(DATA_DIR, "usage.csv")
GROUND_TRUTH_CSV = os.path.join(DATA_DIR, "ground_truth.csv")

# ---- Reference date for the audit ("today") ----
import datetime as _dt
AUDIT_DATE = _dt.date(2026, 6, 26)

# ---- Gemini ----
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
USE_GEMINI = bool(GEMINI_API_KEY)

# ---- Persistence / observability ----
DB_URL = os.getenv("LEAKSENTRY_DB_URL", f"sqlite:///{os.path.join(ROOT, 'leaksentry.db')}")
TRACE_FILE = os.getenv("LEAKSENTRY_TRACE_FILE", os.path.join(ROOT, "traces", "agent_trace.jsonl"))

# ---- Guardrails ----
CONFIDENCE_THRESHOLD = float(os.getenv("LEAKSENTRY_CONFIDENCE_THRESHOLD", "0.6"))
ROUNDING_THRESHOLD = 1.00          # discrepancies below $1 are treated as noise
