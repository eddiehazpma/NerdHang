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


def test_civicplus_rss_parses_and_filters():
    from collector.build import fetch_source
    from collector.fetch_civicplus import parse_civicplus_rss

    src = {"id": "gov-test", "name": "Town", "type": "civicplus_rss", "url": "https://x", "category": "auto",
           "filter": "keywords", "default_location": {"name": "Town", "address": "Babylon, NY"}}
    text = (FIX / "civicplus.xml").read_bytes()
    events = parse_civicplus_rss(text, src, date(2026, 11, 1), date(2027, 3, 1))
    titles = [e.title for e in events]
    assert "Home for the Holidays Pet Adoption Program" not in titles  # 6 weeks long
    train = next(e for e in events if "Train" in e.title)
    assert not train.all_day and train.start.hour == 10 and train.end.hour == 14
    assert train.location.address == "3320 Beltagh Avenue, Wantagh, NY 11793"
    assert train.description == "See the trains run."
    closed = next(e for e in events if "Closed" in e.title)
    assert closed.all_day and closed.location.address == "Babylon, NY"

    class Resp:
        content = text
        def raise_for_status(self): pass
    kept = fetch_source(src, date(2026, 11, 1), date(2027, 3, 1), http_get=lambda url: Resp())
    assert [e.title for e in kept] == ["Holiday Model Train Display"]
    assert kept[0].category == "trains"


def test_retro_gaming_and_open_house_keywords():
    from collector.classify import classify
    assert classify("Long Island Retro Gaming Expo") == "computers"
    assert classify("VCF Tech Swap Meet") == "computers"
    assert classify("Computer Flea Market") == "computers"
    assert classify("Classic Video Games for Seniors") == "computers"
    assert classify("Board Game Night for Adults") is None
    assert classify("Teen Video Game Night") is None
    assert classify("National Weather Service Open House") == "museum"
    assert classify("Fire Department Open House") is None


def test_new_hobby_categories_and_fallback():
    from collector.classify import classify, filter_events
    from collector.models import Event
    assert classify("Long Island Antiquarian Book & Paper Fair") == "records"
    assert classify("Hamptons Record Fair") == "records"
    assert classify("2600 Meeting") == "makers"
    assert classify("Model Ship Building Club") == "makers"
    assert classify("Audubon Bird Walk") == "outdoors"
    assert classify("Metal Detecting 101") == "outdoors"
    assert classify("Montauk Lighthouse Tour") == "outdoors"
    assert classify("Farmers Market") == "fairs"
    assert classify("New York Renaissance Faire") == "fairs"
    assert classify("Polar Express Train Ride") == "trains"
    assert classify("Kids Nature Walk for Toddlers") is None
    assert classify("2600 Merrick Road Cleanup") is None

    def ev(title):
        return Event(source_id="m", source_uid=title, title=title, start=date(2027, 1, 2),
                     end=date(2027, 1, 2), all_day=True, category="other")
    src = {"id": "m", "category": "auto", "filter": "keywords", "fallback_category": "museum"}
    kept = {e.title: e.category for e in filter_events(
        [ev("Dickens in the Carriage Museum"), ev("MUSEUM CLOSED: Thanksgiving Day"), ev("Planetarium Show")], src)}
    assert kept == {"Dickens in the Carriage Museum": "museum", "Planetarium Show": "museum"}


NEWSLETTER = """Hi nerds, here's what's on this week.

[MUSIC] Brooklyn Record Fair
Sat Dec 12, 10am - 5pm
@ Brooklyn Expo Center, 72 Noble Street, Brooklyn, NY
Thousands of LPs, 45s and CDs. https://example.org/recordfair

[ART] Painting the Town
Fri Dec 11, 7pm
Some Gallery, 10 Main St, Brooklyn
https://example.org/art

Vintage Computer Swap Meet - January 9
Bring your old Apple IIs.

View this email in your browser https://example.org/unsubscribe?u=123
"""


def _mail(body, sender="Nonsense NYC <list@nonsensenyc.com>", ics=None):
    from email.message import EmailMessage
    m = EmailMessage()
    m["From"], m["Subject"], m["Date"] = sender, "This week", "Mon, 07 Dec 2026 09:00:00 -0500"
    m["Message-ID"] = "<abc@example>"
    m.set_content(body)
    if ics:
        m.add_attachment(ics, maintype="text", subtype="calendar", filename="invite.ics")
    return m.as_bytes()


def test_inbox_newsletter_parsing():
    from collector.fetch_email import fetch_email
    src = {"id": "inbox", "name": "NerdHang inbox", "type": "email", "category": "auto",
           "senders": [{"match": "nonsensenyc", "name": "Nonsense NYC",
                        "default_location": {"name": "New York City", "address": "New York, NY"}}]}
    events = fetch_email(src, date(2026, 12, 1), date(2027, 6, 1), fetch_messages=lambda: [_mail(NEWSLETTER)])
    by_title = {e.title: e for e in events}
    assert set(by_title) == {"Brooklyn Record Fair", "Vintage Computer Swap Meet"}  # art night has no keyword
    fair = by_title["Brooklyn Record Fair"]
    assert fair.category == "records" and fair.source_name == "Nonsense NYC"
    assert fair.start.hour == 10 and fair.start.day == 12 and fair.start.year == 2026
    assert "72 Noble Street" in fair.location.address and fair.location.name == "Brooklyn Expo Center"
    assert fair.url == "https://example.org/recordfair"
    swap = by_title["Vintage Computer Swap Meet"]
    assert swap.all_day and swap.start == date(2027, 1, 9)  # rolled into next year
    assert swap.location.address == "New York, NY"  # sender default
    assert "unsubscribe" not in " ".join(e.url + e.description for e in events)


def test_inbox_calendar_invite_kept_and_skip_without_secrets(monkeypatch):
    from collector.fetch_email import SkipSource, fetch_email
    ics = (FIX / "rmli.ics").read_bytes()
    src = {"id": "inbox", "name": "NerdHang inbox", "type": "email", "category": "auto"}
    events = fetch_email(src, date(2020, 1, 1), date(2030, 1, 1),
                         fetch_messages=lambda: [_mail("see attached", sender="Pal <pal@example.com>", ics=ics)])
    assert events and all(e.source_name == "Pal" for e in events)
    monkeypatch.delenv("NERDHANG_EMAIL", raising=False)
    monkeypatch.delenv("NERDHANG_APP_PASSWORD", raising=False)
    with pytest.raises(SkipSource):
        fetch_email(src, date(2026, 1, 1), date(2027, 1, 1))


EVENT_PAGE = """<html><head>
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[
 {"@type":"Event","name":"Long Island Antiquarian Book &amp; Paper Fair","startDate":"2027-03-14T10:00:00-04:00",
  "endDate":"2027-03-14T16:00:00-04:00","eventStatus":"https://schema.org/EventScheduled",
  "location":{"@type":"Place","name":"LIU Post","address":{"@type":"PostalAddress","streetAddress":"720 Northern Blvd",
  "addressLocality":"Brookville","addressRegion":"NY","postalCode":"11548"}},"organizer":{"name":"LI Book Dealers"}},
 {"@type":"Event","name":"Online Postcard Show","startDate":"2027-03-20","location":{"@type":"VirtualLocation","url":"https://x"}},
 {"@type":"MusicEvent","name":"Jazz Night","startDate":"2027-03-21","location":"Blue Note, 131 W 3rd St, New York, NY"}
]}</script></head><body></body></html>"""


def test_jsonld_events_and_search(monkeypatch):
    from collector.build import fetch_source
    from collector.fetch_email import SkipSource
    from collector.fetch_web import fetch_search, parse_jsonld_events

    src = {"id": "search", "name": "Web search", "type": "search", "category": "auto", "filter": "keywords",
           "topics": ["book fair"], "areas": ["Long Island NY"], "skip_domains": r"facebook\.com"}
    evs = parse_jsonld_events(EVENT_PAGE, src, "https://example.org/fair", date(2027, 1, 1), date(2027, 12, 31))
    assert sorted(e.title for e in evs) == ["Jazz Night", "Long Island Antiquarian Book & Paper Fair"]  # virtual dropped
    fair = next(e for e in evs if "Book" in e.title)
    assert fair.start.hour == 10 and fair.location.address == "720 Northern Blvd, Brookville, NY, 11548"
    assert fair.source_name == "LI Book Dealers" and fair.url == "https://example.org/fair"

    asked = []

    def api_get(q):
        asked.append(q)
        return {"web": {"results": [{"url": "https://example.org/fair"}, {"url": "https://www.facebook.com/x"}]}}

    class Resp:
        status_code, text, headers = 200, EVENT_PAGE, {"content-type": "text/html"}
    fetched = []
    found = fetch_search(src, date(2027, 1, 1), date(2027, 12, 31),
                         http_get=lambda u: fetched.append(u) or Resp(), api_get=api_get)
    assert asked == ["book fair Long Island NY"] and fetched == ["https://example.org/fair"]
    assert len(found) == 2

    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    with pytest.raises(SkipSource):
        fetch_source(src, date(2027, 1, 1), date(2027, 12, 31), http_get=lambda u: Resp())


def test_limit_repeats_keeps_next_three():
    from collector.build import limit_repeats
    from collector.models import Event
    evs = [Event(source_id="l", source_uid=str(d), title="Adult D&D!" if d % 2 else "adult d&d",
                 start=date(2027, 1, d), end=date(2027, 1, d), all_day=True, category="computers")
           for d in range(10, 1, -1)]
    kept = limit_repeats(evs, 3)
    assert [e.start.day for e in kept] == [2, 3, 4]
