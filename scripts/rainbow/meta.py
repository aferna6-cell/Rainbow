"""Staleness of knowledge/meta/current-meta.md (CLAUDE.md: refresh when >21 days old)."""

import datetime as dt
import re
from pathlib import Path

MAX_AGE_DAYS = 21
VERIFIED_RE = re.compile(r"Last verified:\s*\**(\d{4}-\d{2}-\d{2})\**")


def last_verified(path: Path) -> dt.date | None:
    if not path.exists():
        return None
    m = VERIFIED_RE.search(path.read_text(encoding="utf-8"))
    return dt.date.fromisoformat(m.group(1)) if m else None


def age_days(path: Path, today: dt.date) -> int | None:
    verified = last_verified(path)
    return None if verified is None else (today - verified).days


def is_stale(path: Path, today: dt.date) -> bool:
    age = age_days(path, today)
    return age is None or age > MAX_AGE_DAYS
