"""Deadline arithmetic. Times are Asia/Kolkata; naive datetimes are read as local time."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Kolkata")


def aware(moment: datetime) -> datetime:
    """Return ``moment`` with a timezone, reading naive values as Asia/Kolkata."""
    return moment if moment.tzinfo else moment.replace(tzinfo=LOCAL_TZ)


def is_overdue(deadline: datetime, now: datetime) -> bool:
    """A suggestion is overdue once ``now`` is at or after its deadline."""
    return aware(now) >= aware(deadline)
