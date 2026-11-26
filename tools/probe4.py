import re, requests
from urllib.parse import urljoin
UA = {"User-Agent": "Mozilla/5.0 (compatible; NerdHang-event-calendar/0.1; +https://github.com/eddiehazpma/NerdHang)"}
URLS = """
https://sofo.org/?ical=1
https://sofo.org/calendar/
https://roosevelt.audubon.org/events
https://roosevelt.audubon.org/events/ical
https://www.sandspointpreserveconservancy.org/?ical=1
https://www.sandspointpreserveconservancy.org/calendar/
https://bera.bnl.gov/maker-club/?ical=1
https://bera.bnl.gov/?ical=1
https://www.meetup.com/long-island-maker-space/events/ical/
https://www.meetup.com/long-island-maker-space/events/rss/
https://www.longislandexplorium.org/?ical=1
https://www.longislandexplorium.org/events
https://www.27east.com/events/
https://events.longisland.com/
https://www.2600.com/meetings
https://www.2600.com/meetings/us
https://hicksvillepublicschools.org/gregory-museum
https://longislandmuseum.org/?ical=1
https://www.nonsensenyc.com/
https://www.ltveh.org/recordfair
https://www.vanderbiltmuseum.org/?ical=1
https://www.vanderbiltmuseum.org/events
https://www.lighthousefriends.com/
https://www.montauklighthouse.com/events
https://fireislandlighthouse.com/?ical=1
https://fireislandlighthouse.com/events/
https://www.huntingtonlighthouse.org/events
https://www.oldwestburygardens.org/?ical=1
https://www.plantingfields.org/?ical=1
https://www.licm.org/?ical=1
https://www.longislandaquarium.com/events
https://www.peconiclandtrust.org/?ical=1
https://www.peconiclandtrust.org/events
https://www.seatuck.org/?ical=1
https://www.seatuck.org/events
https://www.caumsettfoundation.org/?ical=1
https://www.ligreenbelt.org/?ical=1
https://www.ligreenbelt.org/hike-schedule
https://www.ctmrf.org/
https://www.wcmrs.org/?ical=1
https://www.longislandsearchandrecovery.com/
https://www.nyrf.com/
https://www.lishipmodelers.org/
https://www.licarshow.org/
""".split()
for url in URLS:
    try:
        r = requests.get(url, headers=UA, timeout=25)
    except Exception as e:
        print(f"\n== {url} ERR {str(e)[:100]}"); continue
    b = r.text; ct = r.headers.get("content-type","").split(";")[0]
    print(f"\n== {url} -> {r.status_code} {ct} {len(b)}B final={r.url}")
    if b.lstrip().startswith("BEGIN:VCALENDAR"):
        print("  ICS", b.count("BEGIN:VEVENT"), [s.strip() for s in re.findall(r"SUMMARY:(.*)", b)][:12]); continue
    if "<rss" in b[:500] or "<feed" in b[:500]:
        print("  RSS", b.count("<item"), re.findall(r"<title>(.*?)</title>", b)[:10]); continue
    if r.status_code != 200: continue
    links = sorted(set(urljoin(r.url, l) for l in re.findall(r'''href=["']([^"']*(?:ical|\.ics|webcal|/feed|rss|calendar/[^"']*)[^"']*)["']''', b, re.I)))
    for l in links[:10]: print("  link:", l[:150])
    for kw in ("tribe-events", "eventbrite", "squarespace", "wix", "localist", "time.ly", "google.com/calendar", "calendar.google", "librarymarket", "mailchimp", "substack"):
        if kw in b.lower(): print("  hint:", kw)
    txt = re.sub(r"<script.*?</script>|<style.*?</style>", " ", b, flags=re.S|re.I)
    txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", txt))
    print("  text:", txt[:400])
