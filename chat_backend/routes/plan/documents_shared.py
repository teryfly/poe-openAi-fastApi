from datetime import datetime
from typing import Optional

from fastapi import HTTPException


def row_to_dict(cursor, row):
    """Convert DB tuple row to dict using cursor columns."""
    columns = [c[0] for c in cursor.description]
    return dict(zip(columns, row))


def iso(dt):
    """Convert datetime to ISO string."""
    return dt.isoformat() if isinstance(dt, datetime) else dt


def to_int_or_none(val: Optional[str]) -> Optional[int]:
    """Convert query string to int; allow None/empty as None."""
    if val is None:
        return None
    s = str(val).strip()
    if s == "":
        return None
    try:
        return int(s)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid integer: {val}")