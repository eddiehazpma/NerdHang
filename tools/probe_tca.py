import re, requests
from collector.geocode import USER_AGENT
for ua in (USER_AGENT, "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"):
    for u in ["https://www.tcatrains.org/events/list/?ical=1", "https://www.tcatrains.org/?ical=1", "https://www.tcatrains.org/events/?ical=1",
              "https://www.tcatrains.org/?post_type=tribe_events&ical=1&eventDisplay=list", "https://www.tcatrains.org/wp-json/tribe/events/v1/events?per_page=5",
              "https://easterntca.com/future-meet-dates/?ical=1", "https://easterntca.com/?ical=1", "https://easterntca.com/events/?ical=1",
              "https://easterntca.com/?post_type=tribe_events&ical=1&eventDisplay=list"]:
        try:
            r = requests.get(u, headers={"User-Agent": ua}, timeout=25)
            b = r.text
            t = (re.search(r"<title>(.*?)</title>", b, re.S) or [None, ""])[1].strip()[:80]
            print(ua[:12], r.status_code, r.headers.get("content-type", "").split(";")[0], len(b), "VEVENTS", b.count("BEGIN:VEVENT"), "|", t, "|", u, "->", r.url)
        except Exception as e:
            print(u, "ERR", str(e)[:80])
