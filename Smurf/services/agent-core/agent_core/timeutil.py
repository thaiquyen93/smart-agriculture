"""Timestamp formatting shared by the state API and the Field IoT tools.

02-agents-and-tools.md A.2: every time field is absolute ISO-8601 with an
explicit offset — never relative ("chiều nay"), never naive/offset-less.
The demo timezone is Vietnam (+07:00), hardcoded rather than read from the
host — the host running agent-core is not guaranteed to be in that zone.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

VN_TZ = timezone(timedelta(hours=7))


def to_iso(epoch_seconds: float) -> str:
    return datetime.fromtimestamp(epoch_seconds, tz=VN_TZ).isoformat(timespec="seconds")
