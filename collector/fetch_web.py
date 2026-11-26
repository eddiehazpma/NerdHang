"""Events from ordinary web pages, found by area searches.

Many event pages describe themselves with schema.org "Event" data (JSON-LD),
the same data Google uses for its event listings. This module:
  * extracts those events from a page (`parse_jsonld_events`), and
  * runs the daily area searches (`fetch_search`): each query goes to the
    Brave Search API, and every result page is checked for Event data.

The search key comes from the BRAVE_SEARCH_API_KEY environment variable
(a GitHub repository secret). Without it the search source is skipped.
"""
from __future__ import annotations

import html
import json
import os
import re
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

from .fetch_email import SkipSource
from .models import Event, Location

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
_LD = re.compile(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", re.S | re.I)


# ---------------------------------------------------------------- JSON-LD

def _walk(data):
    stack = [data]
    while stack:
        d = stack.pop()
        if isinstance(d, list):
            stack.extend(d)
        elif isinstance(d, dict):
            yield d
            for k in ("@graph", "itemListElement", "item", "subEvent", "event", "events"):
                if k in d:
                    stack.append(d[k])


def _is_event(d: dict) -> bool:
    t = d.get("@type")
    types = t if isinstance(t, list) else [t]
    return any(isinstance(x, str) and x.endswith("Event") for x in types)


def _text(v) -> str:
    if isinstance(v, list):
        v = v[0] if v else ""
    if isinstance(v, dict):
        v = v.get("name") or v.get("@value") or ""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(v or "")))).strip()


def _when(v):
    """'2027-04-15', '2027-04-15T10:00:00-04:00' -> date or aware datetime."""
    v = _text(v)
    if not v:
        return None
    try:
        if len(v) <= 10:
            return date.fromisoformat(v)
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        return dt if dt.tzinfo else None  # a time with no zone is ambiguous
    except ValueError:
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None


def _location(loc) -> Location | None:
    if isinstance(loc, list):
        physical = [l for l in loc if not (isinstance(l, dict) and l.get("@type") == "VirtualLocation")]
        loc = physical[0] if physical else None
    if not loc:
        return None
    if isinstance(loc, str):
        return Location(name=loc.split(",")[0].strip(), address=loc)
    if loc.get("@type") == "VirtualLocation":
        return None
    name = _text(loc.get("name"))
    addr = loc.get("address")
    if isinstance(addr, dict):
        parts = [_text(addr.get(k)) for k in ("streetAddress", "addressLocality", "addressRegion", "postalCode")]
        addr = ", ".join(p for p in parts if p)
    else:
        addr = _text(addr)
    out = Location(name=name or addr.split(",")[0], address=addr or name)
    geo = loc.get("geo")
    if isinstance(geo, dict):
        try:
            out.lat, out.lon = float(geo["latitude"]), float(geo["longitude"])
        except (KeyError, TypeError, ValueError):
            pass
    return out if (out.address or out.has_coords) else None


def parse_jsonld_events(page: str, source: dict, page_url: str, window_start: date, window_end: date) -> list[Event]:
    events: list[Event] = []
    for blob in _LD.findall(page):
        try:
            data = json.loads(blob.strip())
        except ValueError:
            continue
        for d in _walk(data):
            if not _is_event(d):
                continue
            if "Cancelled" in _text(d.get("eventStatus")):
                continue
            title, start = _text(d.get("name")), _when(d.get("startDate"))
            location = _location(d.get("location"))
            if not title or start is None or location is None:
                continue  # online-only events or incomplete data
            end = _when(d.get("endDate")) or start
            all_day = not isinstance(start, datetime)
            if all_day:
                end = end.date() if isinstance(end, datetime) else end
            else:
                if not isinstance(end, datetime) or end <= start:
                    end = start + timedelta(hours=2)
            day0 = start if all_day else start.date()
            day1 = end if all_day else end.date()
            if day1 < window_start or day0 > window_end:
                continue
            url = _text(d.get("url")) or page_url
            events.append(Event(
                source_id=source["id"],
                source_uid=f"{url}#{title}@{start.isoformat()}",
                title=title[:140],
                start=start,
                end=end,
                all_day=all_day,
                category=source.get("category", "other"),
                location=location,
                url=url,
                description=_text(d.get("description"))[:500],
                source_name=_text(d.get("organizer")) or urlparse(url).netloc.removeprefix("www."),
            ))
    return events


# ---------------------------------------------------------------- search

def search_queries(source: dict) -> list[str]:
    queries = list(source.get("queries") or [])
    for topic in source.get("topics") or []:
        for area in source.get("areas") or []:
            queries.append(f"{topic} {area}")
    return queries


def fetch_search(source: dict, window_start: date, window_end: date, http_get, api_get=None) -> list[Event]:
    key = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if api_get is None:
        if not key:
            raise SkipSource("search key not set")
        import requests

        def api_get(q):
            r = requests.get(BRAVE_URL, params={"q": q, "count": 20, "country": "us", "search_lang": "en"},
                             headers={"X-Subscription-Token": key, "Accept": "application/json"}, timeout=30)
            r.raise_for_status()
            return r.json()

    skip = re.compile(source.get("skip_domains") or r"(?!x)x", re.I)
    urls: list[str] = []
    for q in search_queries(source):
        for res in (api_get(q).get("web") or {}).get("results") or []:
            u = res.get("url", "")
            if u.startswith("http") and u not in urls and not skip.search(urlparse(u).netloc):
                urls.append(u)
    events: list[Event] = []
    for u in urls[: source.get("max_pages", 60)]:
        try:
            r = http_get(u)
            if r.status_code != 200 or "html" not in r.headers.get("content-type", "html"):
                continue
            events.extend(parse_jsonld_events(r.text, source, u, window_start, window_end))
        except Exception as exc:  # one bad page must not sink the search
            print(f"  search page skipped: {u} ({exc})")
    return events
