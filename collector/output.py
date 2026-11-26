"""Write the collected events as JSON (for the website) and .ics (for calendars)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import icalendar

from .models import Event


def write_json(events: list[Event], path: Path, source_status: dict) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": source_status,
        "events": [e.to_dict() for e in events],
    }
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")


def build_ics(events: list[Event], name: str = "NerdHang") -> bytes:
    cal = icalendar.Calendar()
    cal.add("prodid", "-//NerdHang//Event Calendar//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", name)
    cal.add("refresh-interval", timedelta(hours=12), parameters={"VALUE": "DURATION"})
    stamp = datetime.now(timezone.utc)
    for e in events:
        ve = icalendar.Event()
        ve.add("uid", f"{e.id}@nerdhang")
        ve.add("dtstamp", stamp)
        ve.add("summary", e.title)
        if e.all_day:
            ve.add("dtstart", e.start)
            ve.add("dtend", e.end + timedelta(days=1))  # exclusive in iCalendar
        else:
            ve.add("dtstart", e.start)
            ve.add("dtend", e.end)
        loc = location_text(e)
        if loc:
            ve.add("location", loc)
        if e.location.has_coords:
            ve.add("geo", (e.location.lat, e.location.lon))
        if e.url:
            ve.add("url", e.url)
        desc = "\n\n".join(p for p in [e.description, f"Source: {e.source_name}", e.url] if p)
        ve.add("description", desc)
        ve.add("categories", [e.category])
        cal.add_component(ve)
    return cal.to_ical()


def location_text(e: Event) -> str:
    name, addr = e.location.name, e.location.address
    if addr.startswith(name):
        return addr
    return ", ".join(p for p in (name, addr) if p)


def write_ics(events: list[Event], path: Path) -> None:
    path.write_bytes(build_ics(events))
