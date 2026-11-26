"""One-off: dig into candidate feeds."""
import re, requests
UA = {"User-Agent": "Mozilla/5.0 (compatible; NerdHang-event-calendar/0.1; +https://github.com/eddiehazpma/NerdHang)"}
def get(url):
    try:
        r = requests.get(url, headers=UA, timeout=25); return r
    except Exception as e:
        print("ERR", url, str(e)[:120]); return None
# 1. raw CivicPlus RSS item
for base in ["https://www.nassaucountyny.gov", "https://hempsteadny.gov", "https://www.brookhavenny.gov", "https://www.smithtownny.gov", "https://www.townofbabylonny.gov", "https://www.longbeachny.gov", "https://www.northhempsteadny.gov", "https://islipny.gov", "https://www.huntingtonny.gov"]:
    r = get(base + "/RSSFeed.aspx?ModID=58&CID=All-calendar.xml")
    if r is not None:
        print(f"\n## RSS {base} {r.status_code} items={r.text.count('<item')}")
        m = re.search(r"<item>.*?</item>", r.text, re.S)
        if m: print(m.group(0)[:1500])
    r = get(base + "/calendar.aspx")
    if r is not None and r.status_code == 200:
        cids = sorted(set(re.findall(r'CID=(\d+)', r.text)))
        print(f"## calendar.aspx CIDs: {cids[:30]}")
        for cid in cids[:2]:
            r2 = get(f"{base}/common/modules/iCalendar/iCalendar.aspx?catID={cid}&feed=calendar")
            if r2 is not None: print(f"   ics cat {cid}: {r2.status_code} {r2.headers.get('content-type')} events={r2.text.count('BEGIN:VEVENT')} {r2.text[:80]!r}")
# 2. other pages
for url in ["https://www.longbeachny.gov/events", "https://www.longbeachny.gov/seniorcalendar",
            "https://calendar.time.ly/4uwhqg06", "https://calendar.time.ly/4uwhqg06/export/ics",
            "https://www.liherald.com/calendar/", "https://www.liherald.com/events/?list_type=featured",
            "https://www.newsday.com/json/lifestyle/long-island-events",
            "https://www.bnl.gov/events/", "https://www.bnl.gov/community/",
            "https://www.northhempsteadny.gov/calendar.php", "https://parks.ny.gov/visit/events",
            "https://vintagecomputerfederation.org/events/", "https://vcfed.org/events/",
            "https://www.liretrogamers.com/", "https://www.longislandretrogamingexpo.com/",
            "https://www.lirge.com/", "https://www.retroworldexpo.com/"]:
    r = get(url)
    if r is None: continue
    b = r.text
    print(f"\n## {url} -> {r.status_code} {r.headers.get('content-type','').split(';')[0]} {len(b)}B final={r.url}")
    if b.startswith("BEGIN:VCALENDAR"): print("  ICS events", b.count("BEGIN:VEVENT"), re.findall(r"SUMMARY:(.*)", b)[:10])
    elif r.status_code == 200:
        for l in sorted(set(re.findall(r'''["']([^"'\s]*(?:ical|\.ics|webcal|/feed|rss|json|api/)[^"'\s]*)["']''', b, re.I)))[:20]: print("  link:", l[:160])
        txt = re.sub(r"<script.*?</script>|<style.*?</style>", " ", b, flags=re.S)
        txt = re.sub(r"<[^>]+>", " ", txt); txt = re.sub(r"\s+", " ", txt)
        print("  text:", txt[:900])
