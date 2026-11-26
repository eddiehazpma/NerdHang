"""One-off: look for event feeds on candidate sites."""
import re, sys, requests
from urllib.parse import urljoin
UA = {"User-Agent": "Mozilla/5.0 (compatible; NerdHang-event-calendar/0.1; +https://github.com/eddiehazpma/NerdHang)"}
SITES = {
 "liherald": ["https://www.liherald.com/", "https://www.liherald.com/calendar", "https://www.liherald.com/events"],
 "newsday": ["https://www.newsday.com/", "https://www.newsday.com/lifestyle/things-to-do", "https://www.newsday.com/events"],
 "news12": ["https://longisland.news12.com/", "https://longisland.news12.com/community-calendar", "https://longisland.news12.com/events"],
 "holyblack": ["https://www.theholyblack.com/", "https://www.theholyblack.com/events", "https://www.theholyblack.com/shows", "https://www.theholyblack.com/?ical=1"],
 "orderholyblack": ["https://orderoftheholyblack.com/", "https://orderoftheholyblack.com/events", "https://orderoftheholyblack.com/?ical=1"],
 "longbeach": ["https://www.longbeachny.gov/", "https://www.longbeachny.gov/calendar.aspx", "https://www.longbeachny.gov/index.asp?SEC=&Type=B_EV", "https://www.longbeachny.gov/RSSFeed.aspx?ModID=58&CID=All-calendar.xml"],
 "nassau": ["https://www.nassaucountyny.gov/calendar.aspx", "https://www.nassaucountyny.gov/RSSFeed.aspx?ModID=58&CID=All-calendar.xml", "https://www.nassaucountyny.gov/common/modules/iCalendar/iCalendar.aspx?feed=calendar&catID=All"],
 "suffolk": ["https://www.suffolkcountyny.gov/", "https://www.suffolkcountyny.gov/Calendar"],
 "hempstead": ["https://hempsteadny.gov/", "https://hempsteadny.gov/calendar.aspx", "https://hempsteadny.gov/RSSFeed.aspx?ModID=58&CID=All-calendar.xml"],
 "oysterbay": ["https://oysterbaytown.com/", "https://oysterbaytown.com/calendar/", "https://oysterbaytown.com/?ical=1"],
 "northhempstead": ["https://www.northhempsteadny.gov/", "https://www.northhempsteadny.gov/calendar.aspx", "https://www.northhempsteadny.gov/RSSFeed.aspx?ModID=58&CID=All-calendar.xml"],
 "huntington": ["https://www.huntingtonny.gov/", "https://huntingtonny.gov/calendar.aspx", "https://huntingtonny.gov/RSSFeed.aspx?ModID=58&CID=All-calendar.xml"],
 "islip": ["https://islipny.gov/", "https://islipny.gov/calendar.aspx", "https://islipny.gov/RSSFeed.aspx?ModID=58&CID=All-calendar.xml"],
 "brookhaven": ["https://www.brookhavenny.gov/", "https://www.brookhavenny.gov/calendar.aspx", "https://www.brookhavenny.gov/RSSFeed.aspx?ModID=58&CID=All-calendar.xml"],
 "babylon": ["https://www.townofbabylonny.gov/", "https://www.townofbabylonny.gov/calendar.aspx", "https://www.townofbabylonny.gov/RSSFeed.aspx?ModID=58&CID=All-calendar.xml"],
 "smithtown": ["https://www.smithtownny.gov/", "https://www.smithtownny.gov/calendar.aspx", "https://www.smithtownny.gov/RSSFeed.aspx?ModID=58&CID=All-calendar.xml"],
 "nysparks": ["https://parks.ny.gov/events/", "https://parks.ny.gov/events/feed"],
}
LINK = re.compile(r'''(?:href|src)=["']([^"']*(?:ical|\.ics|webcal|rss|/feed|calendar|events?|cityspark|evvnt|localist)[^"']*)["']''', re.I)
for site, urls in SITES.items():
    print(f"\n##### {site}")
    for url in urls:
        try:
            r = requests.get(url, headers=UA, timeout=25)
            ct = r.headers.get("content-type", ""); body = r.text
            print(f"== {url} -> {r.status_code} {ct.split(';')[0]} {len(body)}B final={r.url}")
            if "calendar" in ct or body.startswith("BEGIN:VCALENDAR"):
                print(f"   ICS {body.count('BEGIN:VEVENT')} events:", [t.strip() for t in re.findall(r'SUMMARY:(.*)', body)][:8])
            elif "xml" in ct or body.lstrip().startswith("<?xml"):
                print(f"   XML items {body.count('<item')}:", re.findall(r'<title>(.*?)</title>', body)[:8])
            elif r.status_code == 200:
                links = []
                for l in LINK.findall(body):
                    u = urljoin(r.url, l)
                    if u not in links and not re.search(r"\.(css|js|png|jpg|svg|woff)", u): links.append(u)
                for l in links[:18]: print("   link:", l[:180])
                for kw in ("cityspark", "evvnt", "localist", "tribe-events", "eventbrite", "squarespace", "wix", "civicplus", "bandsintown", "songkick"):
                    if kw in body.lower(): print("   platform hint:", kw)
        except Exception as e:
            print(f"== {url} -> ERROR {str(e)[:150]}")
