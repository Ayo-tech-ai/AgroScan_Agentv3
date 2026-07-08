"""
tools.py

The ADK-facing bridge functions: the actual "Tools" the Agent
calls. Each function delegates to FarmRecordService for the real
logic, and handles string-coercion of numeric arguments (Groq,
our primary model, sometimes sends numbers as strings).

Add a new tool here, then wrap it with FunctionTool at the bottom
and import it into agent.py's tools=[...] list.
"""

from typing import Optional

from google.adk.tools import FunctionTool

from .database import DATABASE_NAME
from .service import FarmRecordService


# Single shared service instance for this module.
farm_service = FarmRecordService(DATABASE_NAME)


# ============================================================
# STRING-COERCION HELPERS
# Tolerate numeric values sent as strings (e.g. "30" instead of
# 30), and strip common currency formatting a model or farmer
# might include (₦, $, commas, "naira", "usd").
# ============================================================

def _clean_numeric_string(value):
    cleaned = value.strip().lower()
    if cleaned in ("", "null", "none"):
        return None
    for symbol in ["₦", "$", ",", "naira", "usd"]:
        cleaned = cleaned.replace(symbol, "")
    return cleaned.strip()


def _to_int(value, field_name):
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = _clean_numeric_string(value)
        if cleaned is None or cleaned == "":
            return None
        try:
            return int(float(cleaned))
        except ValueError:
            raise ValueError(f"Could not interpret '{value}' as a whole number for {field_name}.")
    return int(value)


def _to_float(value, field_name):
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = _clean_numeric_string(value)
        if cleaned is None or cleaned == "":
            return None
        try:
            return float(cleaned)
        except ValueError:
            raise ValueError(f"Could not interpret '{value}' as a number for {field_name}.")
    return float(value)


# ============================================================
# AGENT ACTION 1 — Record or update daily farm data
# ============================================================

def record_daily_farm_data(
    crates_collected: Optional[str] = None,
    bird_count: Optional[str] = None,
    feed_consumed_kg: Optional[str] = None,
    expenses: Optional[str] = None,
    notes: Optional[str] = None,
    record_date: Optional[str] = None,
):
    """
    Record or update daily poultry farm production.

    Use this action whenever the farmer provides
    daily production information.

    NOTE: All numeric fields are accepted as text and converted
    internally to numbers, to tolerate models that pass numeric
    values as strings.

    If record_date is not provided, it defaults to today's date
    automatically — do not ask the farmer for the date unless
    they are referring to a specific past day.

    Business Rules

    - If a record already exists for the date, it is updated —
      only the fields provided are changed; all other fields,
      including crates_collected, keep their current values.
    - If no record exists yet for the date, missing fields are
      inherited from the most recent prior record. The very
      first record ever created requires all fields.
    - Revenue is calculated automatically.
    - The result includes 'previous_values' (the record's state
      before this call, or None if this created a new record).
    """
    parsed_crates = _to_int(crates_collected, "crates_collected")
    parsed_bird_count = _to_int(bird_count, "bird_count")
    parsed_feed = _to_float(feed_consumed_kg, "feed_consumed_kg")
    parsed_expenses = _to_float(expenses, "expenses")

    return farm_service.record_daily_farm_data(
        crates_collected=parsed_crates,
        bird_count=parsed_bird_count,
        feed_consumed_kg=parsed_feed,
        expenses=parsed_expenses,
        notes=notes,
        record_date=record_date,
    )


# ============================================================
# AGENT ACTION 2 — Exact-date lookup
# ============================================================

def get_farm_record(record_date: str):
    """
    Retrieve the farm record for one exact calendar date.

    Use this when the farmer asks about a SPECIFIC date — including
    relative terms like "yesterday" or "last Tuesday" that you have
    already converted into an exact date (YYYY-MM-DD) before calling
    this tool.

    This performs an EXACT match only. If no record exists for that
    exact date, it returns a clear "no record found" result — it does
    NOT fall back to the nearest available date.

    Args:
        record_date: The exact date to look up, in YYYY-MM-DD format.
    """
    record = farm_service.get_record_by_date(record_date)

    if record is None:
        return {
            "found": False,
            "record_date": record_date,
            "message": f"No farm record was found for {record_date}."
        }

    return {
        "found": True,
        "record_date": record_date,
        "record": record
    }


# ============================================================
# AGENT ACTION 3 — Most recent record
# ============================================================

def get_most_recent_farm_record():
    """
    Retrieve the single most recent farm record in the entire record
    book, regardless of how many days ago it was.

    Use this when the farmer asks something like "what's my last
    record?" or "show me my most recent entry" — situations where
    they want the latest available data, not a specific date.
    """
    record = farm_service.get_most_recent_record()

    if record is None:
        return {"found": False, "message": "No farm records exist yet."}

    return {"found": True, "record": record}


# ============================================================
# AGENT ACTION 4 — Period summary
# ============================================================

def get_farm_summary(start_date: str, end_date: str):
    """
    Get a summary of farm performance over a date range (inclusive
    of both start_date and end_date).

    Use this when the farmer asks about totals or profit/loss over
    a period. Convert relative period references into exact
    YYYY-MM-DD start and end dates BEFORE calling this tool.

    Returns total crates collected, total feed consumed, total
    revenue, total expenses, net profit, and days_recorded. If
    days_recorded is 0, no data exists for that range at all.

    Args:
        start_date: Start of the range, in YYYY-MM-DD format.
        end_date: End of the range, in YYYY-MM-DD format.
    """
    return farm_service.get_summary(start_date, end_date)


# ============================================================
# WRAP AS ADK TOOLS
# These are the objects imported by agent.py.
# ============================================================

farm_record_tool = FunctionTool(record_daily_farm_data)
farm_record_lookup_tool = FunctionTool(get_farm_record)
most_recent_record_tool = FunctionTool(get_most_recent_farm_record)
farm_summary_tool = FunctionTool(get_farm_summary)
