from datetime import datetime, timezone


def utcnow_naive() -> datetime:
    """Return UTC without tzinfo for compatibility with existing DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
