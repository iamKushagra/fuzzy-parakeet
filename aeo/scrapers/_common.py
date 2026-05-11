"""Shared scraper helpers."""
from datetime import datetime, timedelta, timezone


def google_lookback_tbs(lookback_hours: int) -> str:
    """Map a lookback window in hours to a Google Search `tbs=` value.

    Google supports the coarse `qdr:` buckets and a `cdr:` custom date range.
    We pick the tightest bucket that covers the window, falling back to an
    explicit MM/DD/YYYY range for windows >365 days.
    """
    h = max(1, int(lookback_hours))
    if h <= 24:    return "qdr:d"
    if h <= 168:   return "qdr:w"
    if h <= 720:   return "qdr:m"
    if h <= 8760:  return "qdr:y"
    end = datetime.now(tz=timezone.utc)
    start = end - timedelta(hours=h)
    return (
        f"cdr:1,cd_min:{start.month}/{start.day}/{start.year},"
        f"cd_max:{end.month}/{end.day}/{end.year}"
    )
