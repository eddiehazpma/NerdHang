"""Read events from the NerdHang inbox (newsletters and calendar invites).

The inbox address and its Gmail *app password* come from the environment
(GitHub repository secrets NERDHANG_EMAIL and NERDHANG_APP_PASSWORD). Nothing
about the mailbox is stored in the repository. Without the secrets the source
is skipped, so tests and forks still work.

Each run re-reads the last `days_back` days of mail (read-only, nothing is
marked or deleted), so there is no state to keep between runs.

Two kinds of mail are understood:
  * .ics attachments / calendar invites (Eventbrite, Meetup, a friend
    forwarding an invite): parsed exactly, like any iCal feed.
  * Newsletters: plain text is split into blocks, and a block that has a date
    and a NerdHang keyword in its title becomes an event. Newsletter senders
    can be listed in sources.yaml with a default location.
"""
from __future__ import annotations

import email
import html
import imaplib
import os
import re
from datetime import date, datetime, timedelta
from email import policy
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from .classify import filter_events
from .fetch_ics import parse_ics
from .models import Event, Location

TZ = ZoneInfo("America/New_York")
IMAP_HOST = "imap.gmail.com"


class SkipSource(Exception):
    """The source can't run here (e.g. no secrets) and that's expected."""


# ---------------------------------------------------------------- mailbox

def _imap_messages(user: str, password: str, days_back: int, limit: int) -> list[bytes]:
    box = imaplib.IMAP4_SSL(IMAP_HOST)
    try:
        box.login(user, password)
        box.select("INBOX", readonly=True)
        since = (date.today() - timedelta(days=days_back)).strftime("%d-%b-%Y")
        _, data = box.search(None, "SINCE", since)
        ids = data[0].split()[-limit:]
        raw = []
        for i in ids:
            _, parts = box.fetch(i, "(BODY.PEEK[])")
            for p in parts:
                if isinstance(p, tuple):
                    raw.append(p[1])
        return raw
    finally:
        try:
            box.logout()
        except Exception:
            pass


def fetch_email(source: dict, window_start: date, window_end: date, fetch_messages=None) -> list[Event]:
    if fetch_messages is None:
        user = os.environ.get("NERDHANG_EMAIL", "").strip()
        password = os.environ.get("NERDHANG_APP_PASSWORD", "").replace(" ", "").strip()
        if not user or not password:
            raise SkipSource("inbox secrets not set")
        days, limit = source.get("days_back", 60), source.get("max_messages", 300)
        fetch_messages = lambda: _imap_messages(user, password, days, limit)  # noqa: E731
    events: list[Event] = []
    for raw in fetch_messages():
        msg = email.message_from_bytes(raw, policy=policy.default)
        events.extend(events_from_message(msg, source, window_start, window_end))
    return events


# ---------------------------------------------------------------- messages

def _sender_config(msg, source: dict) -> dict:
    sender = f"{msg.get('From', '')} {msg.get('List-Id', '')}".lower()
    for s in source.get("senders") or []:
        if s["match"].lower() in sender:
            return s
    return {}


def events_from_message(msg, source: dict, window_start: date, window_end: date) -> list[Event]:
    cfg = _sender_config(msg, source)
    sub = dict(source)
    sub["name"] = cfg.get("name") or _display_name(msg.get("From", "")) or source.get("name", "Inbox")
    if cfg.get("default_location"):
        sub["default_location"] = cfg["default_location"]
    else:
        sub.pop("default_location", None)

    events: list[Event] = []
    calendars = [p for p in msg.walk()
                 if p.get_content_type() == "text/calendar"
                 or (p.get_filename() or "").lower().endswith(".ics")]
    for part in calendars:
        payload = part.get_payload(decode=True)
        if payload:
            events.extend(parse_ics(payload, sub, window_start, window_end))
    if events:
        for e in events:
            e.source_name = sub["name"]
        return events

    text = _body_text(msg)
    try:
        sent = parsedate_to_datetime(msg.get("Date")).date()
    except Exception:
        sent = date.today()
    msg_id = (msg.get("Message-ID") or "").strip("<> ") or msg.get("Subject", "")
    # Newsletters list everything, so only keyword matches are kept. Invites
    # (above) are kept as they are: someone sent them on purpose.
    found = parse_newsletter(text, sent, sub, window_start, window_end, msg_id)
    return filter_events(found, {**sub, "filter": "keywords"})


def _display_name(from_header: str) -> str:
    name = re.sub(r"<[^>]*>", "", from_header).strip().strip('"')
    return "" if "@" in name else name


def _body_text(msg) -> str:
    plain = msg.get_body(preferencelist=("plain",))
    if plain is not None:
        return plain.get_content()
    rich = msg.get_body(preferencelist=("html",))
    return html_to_text(rich.get_content()) if rich is not None else ""


def html_to_text(markup: str) -> str:
    s = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", " ", markup)
    s = re.sub(r'(?is)<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r"\2 \1 ", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|li|tr|h[1-6]|table)>", "\n\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    return re.sub(r"\n\s*\n\s*(\n\s*)+", "\n\n", s)


# ---------------------------------------------------------------- newsletters

_MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
_MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
_DAY = r"(mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?"
_DATE_WORDS = re.compile(rf"\b(?:{_DAY},?\s+)?{_MON}\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(\d{{4}}))?", re.I)
_DATE_SLASH = re.compile(rf"\b{_DAY},?\s+(\d{{1,2}})/(\d{{1,2}})(?:/(\d{{2,4}}))?\b", re.I)
_TIME = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?\b", re.I)
_URL = re.compile(r"https?://[^\s<>\"')\]]+")
_JUNK_URL = re.compile(r"unsubscribe|list-manage|manage|preferences|mailto:|optout|opt-out|view.*browser|forward", re.I)
_ADDRESS = re.compile(
    r"\b\d{1,5}\s+(?:[NSEW]\.?\s+)?[A-Z0-9][\w.']*(?:\s+[A-Z0-9][\w.']*){0,4}\s+"
    r"(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Pl|Place|Dr|Drive|Ln|Lane|Hwy|Highway|Pkwy|Parkway|"
    r"Tpke|Turnpike|Way|Ct|Court|Sq|Square)\b\.?(?:,\s*[A-Z][\w .']+){0,2}(?:,?\s*(?:NY|NJ|CT)(?:\s+\d{5})?)?")
_AT_VENUE = re.compile(r"(?:^|\s)(?:@|at)\s+([A-Z][\w&'.-]*(?:\s+(?:[A-Z][\w&'.-]*|of|the|and|&)){0,6}(?:,\s*[A-Z][\w.' ]+)?)")
_JUNK_LINE = re.compile(r"^(?:view (?:this|in)|unsubscribe|forward|share|follow us|copyright|©|you are receiving)", re.I)


def _find_date(block: str, sent: date) -> tuple[date, int, int] | None:
    m = _DATE_WORDS.search(block)
    if m:
        month = _MONTHS.index(m.group(2).lower()[:3]) + 1
        day, year = int(m.group(3)), m.group(4)
    else:
        m = _DATE_SLASH.search(block)
        if not m:
            return None
        month, day, year = int(m.group(2)), int(m.group(3)), m.group(4)
    try:
        if year:
            y = int(year)
            d = date(y + 2000 if y < 100 else y, month, day)
        else:
            d = date(sent.year, month, day)
            if d < sent - timedelta(days=14):  # "Jan 5" in a December newsletter
                d = date(sent.year + 1, month, day)
    except ValueError:
        return None
    return d, m.start(), m.end()


def _title(lines: list[str], date_span: tuple[int, int], block: str) -> str:
    for line in lines:
        start = block.find(line)
        if start <= date_span[0] < start + len(line):
            # the date is on this line: use what comes before it, if anything
            before = line[: date_span[0] - start].strip(" -–—|:,")
            if len(before) >= 6:
                line = before
            else:
                continue
        line = _URL.sub("", line)
        line = re.sub(r"^[\s*•·\-–—>#]+|^\[[^\]]{1,20}\]\s*", "", line).strip(" -–—|:")
        if len(line) >= 4 and not _JUNK_LINE.match(line):
            return line[:140]
    return ""


def parse_newsletter(text: str, sent: date, source: dict, window_start: date, window_end: date,
                     msg_id: str = "") -> list[Event]:
    events: list[Event] = []
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block or len(block) > 2500:
            continue
        found = _find_date(block, sent)
        if not found:
            continue
        day, ds, de = found
        if not (window_start <= day <= window_end):
            continue
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        title = _title(lines, (ds, de), block)
        if not title:
            continue
        tm = _TIME.search(block, de) or _TIME.search(block)
        if tm:
            hour = int(tm.group(1)) % 12 + (12 if tm.group(3).lower() == "p" else 0)
            start = datetime(day.year, day.month, day.day, hour, int(tm.group(2) or 0), tzinfo=TZ)
            end, all_day = start + timedelta(hours=2), False
        else:
            start = end = day
            all_day = True
        urls = [u.rstrip(".,;") for u in _URL.findall(block) if not _JUNK_URL.search(u)]
        location = Location()
        addr = _ADDRESS.search(block)
        venue = _AT_VENUE.search(block)
        if addr:
            location = Location(name=(venue.group(1).split(",")[0] if venue else addr.group(0).split(",")[0]),
                                address=addr.group(0))
        elif venue and "," in venue.group(1):
            location = Location(name=venue.group(1).split(",")[0], address=venue.group(1))
        elif source.get("default_location"):
            location = Location(**source["default_location"])
        desc = re.sub(r"\s+", " ", _URL.sub("", block)).strip()
        events.append(Event(
            source_id=source["id"],
            source_uid=f"{msg_id}:{title}@{start.isoformat()}",
            title=title,
            start=start,
            end=end,
            all_day=all_day,
            category=source.get("category", "other"),
            location=location,
            url=urls[0] if urls else "",
            description=desc[:500],
            source_name=source.get("name", source["id"]),
        ))
    return events
