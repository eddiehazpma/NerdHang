"""Hand-entered events from a YAML file."""
from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from .models import Event, Location

EASTERN = ZoneInfo("America/New_York")


def _as_date(v) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v))


def load_manual(path: Path, source: dict, window_start: date, window_end: date) -> list[Event]:
    data = yaml.safe_load(path.read_text()) or {}
    events = []
    for i, e in enumerate(data.get("events") or []):
        start_d = _as_date(e["start"])
        end_d = _as_date(e.get("end", e["start"]))
        if end_d < window_start or start_d > window_end:
            continue
        tz = ZoneInfo(e.get("timezone", "America/New_York"))
        if e.get("start_time"):
            start = datetime.combine(start_d, time.fromisoformat(str(e["start_time"])), tz)
            end = datetime.combine(end_d, time.fromisoformat(str(e.get("end_time", e["start_time"]))), tz)
            all_day = False
        else:
            start, end, all_day = start_d, end_d, True
        events.append(
            Event(
                source_id=source["id"],
                source_uid=e.get("id") or f"{e['title']}@{start_d}",
                title=e["title"],
                start=start,
                end=end,
                all_day=all_day,
                category=e.get("category", "other"),
                location=Location(**(e.get("location") or {})),
                url=e.get("url", ""),
                description=e.get("description", ""),
                source_name=e.get("source_note") or source.get("name", ""),
            )
        )
    return events
