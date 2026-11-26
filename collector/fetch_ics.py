"""Turn an iCalendar (.ics) feed into NerdHang events."""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone

import icalendar
import recurring_ical_events

from .models import Event, Location

# A LOCATION this short or vague (e.g. "NY") is no use for a map.
_VAGUE_LOCATION = re.compile(r"^\s*([A-Za-z]{2}|USA?|United States|TBD|TBA)?\s*$", re.I)
# On-air or online "locations" (repeater frequencies, Zoom) are not places.
_VIRTUAL_LOCATION = re.compile(r"zoom|online|virtual|repeater|\bmhz\b|\b\d{2,3}\.\d{2,3}\b|^[^A-Za-z]*$", re.I)


def _clean(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _to_all_day(start, end):
    """Return (start_date, inclusive_end_date) if the event is really all-day.

    Covers true DATE values and feeds that fake all-day events as
    00:00 to 23:59 (Eastern TCA does this).
    """
    if not isinstance(start, datetime):
        end_d = end if end is not None else start
        if isinstance(end_d, datetime):
            end_d = end_d.date()
        # iCalendar DTEND for dates is exclusive.
        if end_d > start:
            end_d = end_d - timedelta(days=1)
        return start, end_d
    if end is not None and isinstance(end, datetime):
        if start.time() == time(0, 0) and end.time() >= time(23, 59) and end.date() >= start.date():
            return start.date(), end.date()
    return None


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def parse_ics(text: str | bytes, source: dict, window_start: date, window_end: date) -> list[Event]:
    cal = icalendar.Calendar.from_ical(text)
    occurrences = recurring_ical_events.of(cal).between(window_start, window_end)
    exclude = re.compile(source["exclude_titles"], re.I) if source.get("exclude_titles") else None
    events: list[Event] = []
    for comp in occurrences:
        if _clean(comp.get("STATUS")).upper() == "CANCELLED":
            continue
        title = _clean(comp.get("SUMMARY"))
        if not title or (exclude and exclude.search(title)):
            continue
        start = comp.decoded("DTSTART")
        end = comp.decoded("DTEND") if comp.get("DTEND") else None

        all_day = _to_all_day(start, end)
        if all_day:
            start_v, end_v = all_day
        else:
            start_v = _aware(start)
            end_v = _aware(end) if isinstance(end, datetime) else start_v + timedelta(hours=2)

        uid = _clean(comp.get("UID")) or title
        # Recurring events share a UID; make each occurrence unique.
        uid = f"{uid}@{start_v.isoformat()}"

        loc_text = _clean(comp.get("LOCATION")).replace("\\,", ",")
        location = Location()
        if loc_text and not _VAGUE_LOCATION.match(loc_text) and not _VIRTUAL_LOCATION.search(loc_text):
            name, _, rest = loc_text.partition(",")
            location = Location(name=name.strip(), address=loc_text if rest else "")
        geo = comp.get("GEO")
        if geo is not None:
            location.lat, location.lon = float(geo.latitude), float(geo.longitude)

        if not location.geocode_query():
            location = _location_from_hints(title, source)

        events.append(
            Event(
                source_id=source["id"],
                source_uid=uid,
                title=source.get("title_prefix", "") + title,
                start=start_v,
                end=end_v,
                all_day=bool(all_day),
                category=source.get("category", "other"),
                location=location,
                url=_clean(comp.get("URL")) or source.get("homepage", ""),
                description=_clean(comp.get("DESCRIPTION"))[:500],
                source_name=source.get("name", source["id"]),
            )
        )
    return events


def _location_from_hints(title: str, source: dict) -> Location:
    for key, loc in (source.get("location_hints") or {}).items():
        if key.lower() in title.lower():
            return Location(**loc)
    if source.get("default_location"):
        return Location(**source["default_location"])
    return Location()
