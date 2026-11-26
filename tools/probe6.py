import re, json, requests
UA = {"User-Agent": "Mozilla/5.0 (compatible; NerdHang-event-calendar/0.1; +https://github.com/eddiehazpma/NerdHang)"}
URLS = """
https://www.ephemerasociety.org/events-calendar/
https://www.ephemerasociety.org/?ical=1
https://www.ephemerasociety.org/events/?ical=1
https://bookevents.nyc/long-island
https://thebookfairies.org/calendar/
https://thebookfairies.org/?ical=1
https://getmansvirtual.com/
https://events.longisland.com/long-island-antiquarian-book-and-paper-fair.html
https://www.discoverlongisland.com/partner/gold-coast-book-fair-8008/
https://goldcoastbookfair.com/
https://longislandmuseum.org/event/pagesandpictures/
https://www.nyantiquarianbookfair.com/
https://oysterbaytoday.com/obt-event/gold-coast-book-fair-2025/
https://www.eventbrite.com/d/ny--long-beach/book-fair/
https://allevents.in/long%20island/book-fair
""".split()


def jsonld_events(html):
    out = []
    for blob in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(blob.strip())
        except Exception:
            continue
        stack = [data]
        while stack:
            d = stack.pop()
            if isinstance(d, list):
                stack.extend(d); continue
            if not isinstance(d, dict):
                continue
            t = d.get("@type"); t = t if isinstance(t, list) else [t]
            if any(isinstance(x, str) and x.endswith("Event") for x in t):
                loc = d.get("location") or {}
                if isinstance(loc, list):
                    loc = loc[0] if loc else {}
                out.append((d.get("startDate"), d.get("name"), (loc.get("name") if isinstance(loc, dict) else loc)))
            stack.extend(v for k, v in d.items() if k in ("@graph", "itemListElement", "item", "subEvent", "event", "events"))
    return out


for url in URLS:
    try:
        r = requests.get(url, headers=UA, timeout=25)
    except Exception as e:
        print(f"\n== {url} ERR {str(e)[:90]}"); continue
    b = r.text
    print(f"\n== {url} -> {r.status_code} {r.headers.get('content-type','').split(';')[0]} {len(b)}B final={r.url}")
    if b.lstrip().startswith("BEGIN:VCALENDAR"):
        print("  ICS", b.count("BEGIN:VEVENT"), [s.strip() for s in re.findall(r"SUMMARY:(.*)", b)][:15]); continue
    ev = jsonld_events(b)
    print("  JSON-LD events:", len(ev))
    for e in ev[:12]:
        print("   ", e)
    if r.status_code == 200 and not ev:
        for kw in ("tribe-events", "eventbrite", "wix", "squarespace", "?ical", "webcal", ".ics"):
            if kw in b.lower():
                print("  hint:", kw)
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", b)))
        for m in re.finditer(r"(?i)(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? \d{1,2}(?:[-–]\d{1,2})?,? 20(?:26|27)", txt):
            print("  date:", txt[max(0, m.start()-80):m.end()+20]); break
