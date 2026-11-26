import re, requests
UA = {"User-Agent": "Mozilla/5.0 (compatible; NerdHang-event-calendar/0.1; +https://github.com/eddiehazpma/NerdHang)"}
r = requests.get("https://bookevents.nyc/long-island", headers=UA, timeout=25)
b = r.text
for pat in [r'''["']([^"']*(?:ical|\.ics|webcal|rss|feed|/api/|\.json)[^"']*)["']''']:
    for l in sorted(set(re.findall(pat, b, re.I)))[:30]: print("link:", l[:200])
print("next data:", "__NEXT_DATA__" in b, "self.__next_f" in b)
i = b.find("Sun, Nov 29, 2026"); print(b[max(0,i-1500):i+500])
for u in ["https://bookevents.nyc/long-island.ics", "https://bookevents.nyc/api/events?region=long-island", "https://bookevents.nyc/feed", "https://bookevents.nyc/long-island/feed", "https://bookevents.nyc/rss"]:
    try:
        x = requests.get(u, headers=UA, timeout=20); print("\n==", u, x.status_code, x.headers.get("content-type"), x.text[:200].replace("\n"," "))
    except Exception as e: print(u, e)
