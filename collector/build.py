"""Run every source, merge the results and write data/events.json + data/nerdhang.ics.

Usage:  python -m collector.build
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests
import yaml

from .classify import filter_events
from .fetch_civicplus import parse_civicplus_rss
from .fetch_email import SkipSource, fetch_email
from .fetch_ics import parse_ics
from .fetch_web import fetch_search
from .geocode import USER_AGENT, Geocoder
from .manual import load_manual
from .models import Event
from .output import write_ics, write_json

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def load_sources(path: Path = ROOT / "collector" / "sources.yaml") -> list[dict]:
    return [s for s in yaml.safe_load(path.read_text())["sources"] if s.get("enabled", True)]


def fetch_source(source: dict, window_start: date, window_end: date, http_get=None) -> list[Event]:
    events = filter_events(_fetch_raw(source, window_start, window_end, http_get), source)
    # Club calendars list each meeting once; general calendars repeat weekly clubs.
    keep = source.get("max_repeats", 3 if source.get("filter") == "keywords" else 0)
    return limit_repeats(events, keep) if keep else events


def limit_repeats(events: list[Event], keep: int) -> list[Event]:
    """A weekly club would fill the list with the same title, so only its next
    few dates are kept."""
    seen: dict[str, int] = {}
    out = []
    for e in sorted(events, key=lambda e: e.start_date):
        key = re.sub(r"\W+", " ", e.title.lower()).strip()
        seen[key] = seen.get(key, 0) + 1
        if seen[key] <= keep:
            out.append(e)
    return out


def _fetch_raw(source: dict, window_start: date, window_end: date, http_get=None) -> list[Event]:
    kind = source["type"]
    if kind == "manual":
        return load_manual(ROOT / source["path"], source, window_start, window_end)
    get = http_get or (lambda url: requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30))
    if kind == "ics":
        resp = get(source["url"])
        resp.raise_for_status()
        return parse_ics(resp.content, source, window_start, window_end)
    if kind == "email":
        return fetch_email(source, window_start, window_end)
    if kind == "search":
        return fetch_search(source, window_start, window_end, get)
    if kind == "libcal":
        return _fetch_libcal(source, window_start, window_end, get)
    if kind == "civicplus_rss":
        resp = get(source["url"])
        resp.raise_for_status()
        return parse_civicplus_rss(resp.content, source, window_start, window_end)
    if kind == "ics_links":
        # A listing page that links to one .ics file per event.
        resp = get(source["url"])
        resp.raise_for_status()
        links = []
        for href in re.findall(source["link_pattern"], resp.text):
            url = urljoin(source["url"], html.unescape(href))
            if url not in links:
                links.append(url)
        events: list[Event] = []
        for url in links[: source.get("max_links", 40)]:
            r = get(url)
            r.raise_for_status()
            events.extend(parse_ics(r.content, source, window_start, window_end))
        return events
    raise ValueError(f"unknown source type {kind!r}")


def _fetch_libcal(source: dict, window_start: date, window_end: date, get) -> list[Event]:
    """Springshare LibCal: find the library's public calendar ids from its event
    list, then read each calendar's iCal feed."""
    host = source["host"]
    cids = [str(c) for c in source.get("calendar_ids") or []]
    if not cids:
        for page in (1, 2, 3):
            resp = get(f"https://{host}/ajax/calendar/list?c=-1&date=0000-00-00&perpage=48&page={page}"
                       "&audience=&cats=&camps=&inc=0")
            resp.raise_for_status()
            results = resp.json().get("results") or []
            for e in results:
                cid = str(e.get("calendar_id") or "")
                if cid and cid not in cids:
                    cids.append(cid)
            if len(results) < 48:
                break
    if not cids:
        raise ValueError("no LibCal calendars found")
    events: list[Event] = []
    for cid in cids:
        r = get(f"https://{host}/ical_subscribe.php?src=p&cid={cid}")
        r.raise_for_status()
        events.extend(parse_ics(r.content, source, window_start, window_end))
    return events


def _words(title: str) -> set[str]:
    stop = {"the", "a", "of", "and", "at", "in", "meet", "show", "train", "2026", "2027", "tca"}
    return {w for w in re.findall(r"[a-z0-9]+", title.lower()) if w not in stop}


def _km(a: Event, b: Event) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a.location.lat, a.location.lon, b.location.lat, b.location.lon))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def _richness(e: Event) -> int:
    return len(e.description) + 50 * bool(e.location.address) + 20 * bool(e.url)


def dedupe(events: list[Event]) -> list[Event]:
    """Drop the same event listed twice: same day and either a near-identical
    title, or (from different sources) a venue within 1 km."""
    kept: list[Event] = []
    for e in sorted(events, key=_richness, reverse=True):
        dup = False
        for k in kept:
            if k.start_date != e.start_date:
                continue
            same_title = _words(k.title) == _words(e.title)
            same_place = (
                k.source_id != e.source_id
                and k.location.has_coords
                and e.location.has_coords
                and _km(k, e) < 1.0
            )
            if same_title or same_place:
                dup = True
                break
        if not dup:
            kept.append(e)
    return sorted(kept, key=lambda e: (e.start_date.isoformat(), e.title))


def load_previous(path: Path) -> dict[str, list[Event]]:
    if not path.exists():
        return {}
    by_source: dict[str, list[Event]] = {}
    for d in json.loads(path.read_text()).get("events", []):
        by_source.setdefault(d["source_id"], []).append(Event.from_dict(d))
    return by_source


def run(today: date | None = None, geocode: bool = True, out_dir: Path = DATA, http_get=None) -> int:
    today = today or date.today()
    window_start, window_end = today - timedelta(days=1), today + timedelta(days=548)
    out_dir.mkdir(parents=True, exist_ok=True)
    previous = load_previous(out_dir / "events.json")

    all_events: list[Event] = []
    status: dict[str, dict] = {}
    failures = 0
    for source in load_sources():
        try:
            events = fetch_source(source, window_start, window_end, http_get)
            status[source["id"]] = {"ok": True, "count": len(events)}
            print(f"{source['id']}: {len(events)} events")
        except SkipSource as why:
            status[source["id"]] = {"ok": True, "count": 0, "skipped": str(why)}
            print(f"{source['id']}: skipped ({why})")
            continue
        except Exception as exc:  # one broken site must not stop the rest
            failures += 1
            events = [e for e in previous.get(source["id"], []) if e.start_date >= window_start]
            status[source["id"]] = {"ok": False, "error": str(exc)[:200], "count": len(events)}
            print(f"{source['id']}: FAILED ({exc}); kept {len(events)} events from last run", file=sys.stderr)
        all_events.extend(events)

    if geocode:
        geo = Geocoder(out_dir / "geocache.json")
        for e in all_events:
            if not e.location.has_coords and e.location.geocode_query():
                coords = geo(e.location.geocode_query())
                if coords:
                    e.location.lat, e.location.lon = coords
        geo.save()

    final = dedupe(all_events)
    write_json(final, out_dir / "events.json", status)
    write_ics(final, out_dir / "nerdhang.ics")
    print(f"wrote {len(final)} events ({len(all_events) - len(final)} duplicates removed)")
    # Fail the run only if every source failed, so a single flaky site is not an alarm.
    tried = sum(1 for s in status.values() if not s.get("skipped"))
    return 1 if failures and failures == tried else 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-geocode", action="store_true", help="skip address lookups")
    args = ap.parse_args()
    sys.exit(run(geocode=not args.no_geocode))


if __name__ == "__main__":
    main()
