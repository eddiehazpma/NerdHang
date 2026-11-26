"""Town and county calendars on CivicPlus sites (Nassau, Hempstead, Brookhaven...).

Their calendar RSS feed (RSSFeed.aspx?ModID=58&CID=All-calendar.xml) carries
dates, times and location in calendarEvent:* elements, e.g.
  <calendarEvent:EventDates>November 22, 2026 - January 3, 2027</calendarEvent:EventDates>
  <calendarEvent:EventTimes>10:00 AM - 2:00 PM</calendarEvent:EventTimes>
  <calendarEvent:Location>3320 Beltagh AvenueWantagh, NY 11793</calendarEvent:Location>
"""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .models import Event, Location

TZ = ZoneInfo("America/New_York")


def _child(item: ET.Element, local: str) -> str:
    for el in item:
        if el.tag.split("}")[-1] == local:
            return (el.text or "").strip()
    return ""


def _date(text: str) -> date | None:
    try:
        return datetime.strptime(text.strip(), "%B %d, %Y").date()
    except ValueError:
        return None


def _time(text: str):
    try:
        return datetime.strptime(text.strip().upper().replace(".", ""), "%I:%M %p").time()
    except ValueError:
        return None


def _location(raw: str, source: dict) -> Location:
    # "3320 Beltagh AvenueWantagh, NY 11793": the street and town lines are run
    # together, so put a comma back at the lower→Upper boundary.
    text = re.sub(r"([a-z0-9.])([A-Z][a-z]+(?: [A-Z][a-z]+)*, (?:NY|New York))", r"\1, \2", raw.strip())
    if text:
        return Location(name=text.split(",")[0].strip(), address=text)
    if source.get("default_location"):
        return Location(**source["default_location"])
    return Location()


def parse_civicplus_rss(text: str | bytes, source: dict, window_start: date, window_end: date) -> list[Event]:
    root = ET.fromstring(text)
    events: list[Event] = []
    for item in root.iter("item"):
        title = html.unescape(_child(item, "title"))
        dates = _child(item, "EventDates")
        if not title or not dates:
            continue
        first, _, last = dates.partition(" - ")
        d0 = _date(first)
        d1 = _date(last) if last else d0
        if d0 is None:
            continue
        d1 = d1 or d0
        # Long-running "events" (a month of pet adoptions) aren't shows.
        if (d1 - d0).days > source.get("max_days", 4):
            continue
        if d1 < window_start or d0 > window_end:
            continue
        t0s, _, t1s = _child(item, "EventTimes").partition(" - ")
        t0, t1 = _time(t0s), _time(t1s)
        all_day = t0 is None or (t0.hour == 0 and t0.minute == 0 and (t1 is None or (t1.hour == 23 and t1.minute == 59)))
        if all_day:
            start, end = d0, d1
        else:
            start = datetime.combine(d0, t0, TZ)
            end = datetime.combine(d1 if t1 else d0, t1, TZ) if t1 else start + timedelta(hours=2)
            if end <= start:
                end = start + timedelta(hours=2)
        desc = re.sub(r"<[^>]+>", " ", html.unescape(_child(item, "description")))
        desc = re.sub(r"\s+", " ", desc).strip()
        desc = re.sub(r"^.*?Description:\s*", "", desc) if "Description:" in desc else ""
        link = _child(item, "link")
        events.append(Event(
            source_id=source["id"],
            source_uid=f"{link or title}@{start.isoformat()}",
            title=title,
            start=start,
            end=end,
            all_day=all_day,
            category=source.get("category", "other"),
            location=_location(_child(item, "Location"), source),
            url=link or source.get("homepage", ""),
            description=desc[:500],
            source_name=source.get("name", source["id"]),
        ))
    return events
