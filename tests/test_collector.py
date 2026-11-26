import json
from datetime import date, datetime
from pathlib import Path

import icalendar
import pytest

from collector import build
from collector.fetch_ics import parse_ics
from collector.geocode import Geocoder
from collector.models import Event, Location

FIX = Path(__file__).parent / "fixtures"
START, END = date(2026, 11, 25), date(2028, 5, 25)

RMLI = {
    "id": "rmli", "name": "RMLI", "category": "trains", "homepage": "https://www.rmli.org/",
    "default_location": {"name": "Railroad Museum of Long Island", "address": "416 Griffing Ave, Riverhead, NY 11901"},
    "location_hints": {"Greenport": {"name": "RMLI Greenport", "address": "440 Fourth St, Greenport, NY 11944"}},
}


def test_rmli_vague_location_uses_hints_and_default_and_skips_past():
    events = parse_ics((FIX / "rmli.ics").read_bytes(), RMLI, START, END)
    assert [e.title for e in events] == [
        "Sayville Village Holiday Fair - Toy Train Outreach",
        "Open House with Santa at Greenport",
    ]
    sayville, greenport = events
    assert sayville.location.address.startswith("416 Griffing")  # default (no hint configured here)
    assert greenport.location.name == "RMLI Greenport"
    assert not sayville.all_day
    assert sayville.start.hour == 16 and str(sayville.start.tzinfo) == "America/New_York"


def test_fake_all_day_multi_day_event_becomes_all_day():
    src = {"id": "eastern-tca", "category": "trains", "title_prefix": "York Train Meet: "}
    [e] = parse_ics((FIX / "eastern_tca.ics").read_bytes(), src, START, END)
    assert e.all_day
    assert (e.start, e.end) == (date(2027, 10, 19), date(2027, 10, 23))
    assert e.title == "York Train Meet: October 2027 Meet"
    assert e.location.name == "York Expo Center"
    assert "Carlisle Ave" in e.location.address


def test_recurring_expanded_cancelled_dropped_dates_inclusive():
    src = {"id": "limarc", "category": "ham-radio", "default_location": {"address": "Hicksville, NY"}}
    events = parse_ics((FIX / "recurring.ics").read_bytes(), src, START, END)
    titles = [e.title for e in events]
    assert titles.count("Club Meeting") == 3
    assert "Cancelled Thing" not in titles
    assert len({e.id for e in events}) == len(events)
    [ham] = [e for e in events if e.title == "Spring Hamfest"]
    assert ham.all_day and ham.start == ham.end == date(2027, 3, 20)
    assert ham.location.address == "Hicksville, NY"


def _ev(source, title, day, lat=None, lon=None, desc=""):
    return Event(source, title + str(day), title, day, day, True, "trains",
                 Location("x", "addr", lat, lon), description=desc)


def test_dedupe_same_title_and_cross_source_same_place():
    d = date(2027, 4, 20)
    events = [
        _ev("tca", "TCA Eastern Division York Train Meet", d, 39.95, -76.75),
        _ev("eastern-tca", "York Train Meet: April 2027 Meet", d, 39.951, -76.751, desc="more detail"),
        _ev("tca", "Other Meet Far Away", d, 33.0, -84.0),
        _ev("rmli", "Open House", d, 40.9, -72.6),
        _ev("rmli", "Open House", date(2027, 4, 21), 40.9, -72.6),
        _ev("rmli", "open house!", d),  # same title, same day -> dup
    ]
    out = build.dedupe(events)
    titles = sorted(e.title for e in out)
    assert titles == ["Open House", "Open House", "Other Meet Far Away", "York Train Meet: April 2027 Meet"]


def test_event_roundtrip():
    e = _ev("a", "T", date(2027, 1, 1), 1.0, 2.0)
    assert Event.from_dict(json.loads(json.dumps(e.to_dict()))) == e
    t = Event("a", "u", "T", datetime.fromisoformat("2027-01-01T10:00:00-05:00"),
              datetime.fromisoformat("2027-01-01T12:00:00-05:00"), False, "museum")
    assert Event.from_dict(t.to_dict()) == t


def test_geocoder_caches_and_respects_limit(tmp_path):
    calls = []
    geo = Geocoder(tmp_path / "c.json", lookup=lambda q: calls.append(q) or (1.0, 2.0), max_lookups=1)
    assert geo("Riverhead, NY") == (1.0, 2.0)
    assert geo("riverhead,  ny".replace(",  ", ", ")) == (1.0, 2.0)
    assert geo("Somewhere else") is None  # over the limit, not cached
    geo.save()
    assert calls == ["Riverhead, NY"]
    assert Geocoder(tmp_path / "c.json", lookup=lambda q: pytest.fail())("Riverhead, NY") == (1.0, 2.0)


class FakeResp:
    def __init__(self, content=b"", fail=False):
        self.content, self.fail = content, fail

    def raise_for_status(self):
        if self.fail:
            raise RuntimeError("HTTP 500")


def test_full_run_writes_outputs_and_survives_a_broken_source(tmp_path, monkeypatch):
    feeds = {
        "https://www.rmli.org/events/?ical=1": FakeResp((FIX / "rmli.ics").read_bytes()),
        "https://easterntca.com/future-meet-dates/?ical=1": FakeResp((FIX / "eastern_tca.ics").read_bytes()),
    }
    get = lambda url: feeds.get(url, FakeResp(fail=True))
    code = build.run(today=START, geocode=False, out_dir=tmp_path, http_get=get)
    assert code == 0
    data = json.loads((tmp_path / "events.json").read_text())
    assert data["sources"]["tca"]["ok"] is False
    assert data["sources"]["rmli"]["count"] == 2
    titles = [e["title"] for e in data["events"]]
    assert "Vintage Computer Festival East 2027" in titles  # manual source
    assert titles == sorted(titles, key=lambda t: next(e["start"][:10] for e in data["events"] if e["title"] == t))

    cal = icalendar.Calendar.from_ical((tmp_path / "nerdhang.ics").read_bytes())
    vevents = cal.walk("VEVENT")
    assert len(vevents) == len(data["events"])

    # Next run: RMLI is down, so its events from the last run are kept.
    feeds["https://www.rmli.org/events/?ical=1"] = FakeResp(fail=True)
    build.run(today=START, geocode=False, out_dir=tmp_path, http_get=get)
    data2 = json.loads((tmp_path / "events.json").read_text())
    assert data2["sources"]["rmli"] == {"ok": False, "error": "HTTP 500", "count": 2}


def test_exclude_titles_and_virtual_locations():
    import yaml
    limarc = next(s for s in yaml.safe_load(open("collector/sources.yaml"))["sources"] if s["id"] == "limarc")
    events = parse_ics((FIX / "recurring.ics").read_bytes(), limarc, START, END)
    titles = {e.title for e in events}
    assert "TECH NET" not in titles
    [talk] = [e for e in events if e.title == "Antenna Talk"]
    assert talk.location.address == "Hicksville, NY"  # Zoom is not a place: falls back to the default
    import re
    pat = re.compile(limarc["exclude_titles"], re.I)
    for t in ["Morning Drive-time Net", "Check-inNets", "LIMARC Board Neeting", "Info Ne followed by Swap-n-Shopt", "NC ARES Meeting"]:
        assert pat.search(t), t
    for t in ["LIMARC General Meeting", "Indoor Hamfest", "Spring Hamfest"]:
        assert not pat.search(t), t


def test_geocode_falls_back_to_town_when_venue_unknown(tmp_path):
    from collector.geocode import query_variants
    q = "Ballroom at the Phoenix, 1661 Mill Road, Upper Chichester, Pennsylvania, 19061, United States"
    assert query_variants(q) == [
        "Ballroom at the Phoenix, 1661 Mill Road, Upper Chichester, Pennsylvania, 19061",
        "1661 Mill Road, Upper Chichester, Pennsylvania, 19061",
        "Upper Chichester, Pennsylvania, 19061",
    ]
    known = {"Upper Chichester, Pennsylvania, 19061": (39.8, -75.4)}
    geo = Geocoder(tmp_path / "c.json", lookup=lambda v: known.get(v))
    assert geo(q) == (39.8, -75.4)
    assert len(geo.cache) == 3  # each attempt cached, so the next run makes no requests


@pytest.mark.parametrize("title,desc,expected", [
    ("Model Train Display", "", "trains"),
    ("LIRR History Talk", "", "trains"),
    ("Intro to Amateur Radio", "", "ham-radio"),
    ("Retro Gaming Night at Syosset Public Library", "", "computers"),
    ("Planetarium Show", "", "museum"),
    ("How to Choose and Use Your Telescope (In Person)", "", "museum"),
    ("Holiday Open House", "Come see the model trains running!", "trains"),
    ("Dog Training 101", "", None),
    ("Knitting Circle", "", None),
    ("Computer Basics I", "", None),
    ("CHIP Chat: Computer Classes for Beginners", "", None),
    ("On-Your-Own Train Trip to NYC (off-site)", "", None),
    ("New York Botanical Gardens: Holiday Train Show Bus Trip", "", None),
    ("Highway to Freedom: The Maritime Underground Railroad (Zoom)", "", None),
    ("Point Lookout Book Club: The Last Train to Key West", "", None),
    ("3D Printed Model Train", "", "trains"),
    ("Retro Gaming (Grades 6-12)", "", None),
    ("TEEN: Maker Studio", "", None),
])
def test_classify(title, desc, expected):
    from collector.classify import classify
    assert classify(title, desc) == expected


def test_keyword_filter_on_general_calendar():
    from collector.classify import filter_events
    events = [_ev("lib", "Knitting Circle", date(2027, 1, 5)), _ev("lib", "Lionel Model Train Workshop", date(2027, 1, 6)),
              _ev("lib", "Ham Radio Licensing Session", date(2027, 1, 7))]
    out = filter_events(events, {"filter": "keywords", "category": "auto"})
    assert [(e.title, e.category) for e in out] == [("Lionel Model Train Workshop", "trains"), ("Ham Radio Licensing Session", "ham-radio")]
    # A specialist source without a filter keeps everything and its category.
    assert len(filter_events(events, {"category": "trains"})) == 3


def test_ics_links_source_and_always_default_location():
    src = {"id": "museum", "type": "ics_links", "category": "museum", "url": "https://m.example/cal.html",
           "link_pattern": r'href="([^"]*/ical/[^"]+)"', "always_default_location": True,
           "default_location": {"name": "The Museum", "address": "1 Main St, Garden City, NY"}}
    page = FakeResp(b'<a href="/ical/1">a</a> <a href="/ical/1">dup</a> <a href="https://m.example/ical/2">b</a>')
    page.text = page.content.decode()
    pages = {"https://m.example/cal.html": page,
             "https://m.example/ical/1": FakeResp((FIX / "eastern_tca.ics").read_bytes()),
             "https://m.example/ical/2": FakeResp((FIX / "rmli.ics").read_bytes())}
    events = build.fetch_source(src, START, END, http_get=lambda u: pages[u])
    assert len(events) == 3  # 1 from the first link, 2 upcoming from the second; duplicate link fetched once
    assert {e.location.name for e in events} == {"The Museum"}
