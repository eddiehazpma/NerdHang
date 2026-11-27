import re, requests, concurrent.futures as cf
UA = {"User-Agent": "Mozilla/5.0 (compatible; NerdHang-event-calendar/0.1; +https://github.com/eddiehazpma/NerdHang)"}
HOSTS = """bryantlibrary eastmeadow elmontlibrary floralparklibrary franklinsquarepl freeportlibrary gardencitypl glencovelibrary
greatnecklibrary hempsteadlibrary hicksvillelibrary hillsidelibrary huntingtonlibrary hwpl islandparklibrary johnjermain
lakeviewlibrary longwood northbellmorelibrary oceansidelibrary plainedgelibrary rvcpl seaclifflibrary wantaghlibrary westburylibrary""".split()
def check(h):
    out = [h]
    try:
        r = requests.get(f"https://{h}.libcal.com/calendar", headers=UA, timeout=20)
        b = r.text
        ids = set(re.findall(r'(?:cid|calendar_id|calendarId|"cal_id")["\s:=]+["\']?(\d{3,6})', b))
        ids |= set(re.findall(r'/calendar/[^"\']*\?cid=(\d+)', b))
        ids |= set(re.findall(r'data-cid=["\'](\d+)', b))
        slugs = sorted(set(re.findall(r'href=["\'](?:https://%s\.libcal\.com)?/calendar/([a-z0-9_-]+)' % h, b)))[:8]
        out += [r.url, sorted(ids)[:8], slugs]
        for cid in sorted(ids)[:4]:
            x = requests.get(f"https://{h}.libcal.com/ical_subscribe.php?src=p&cid={cid}", headers=UA, timeout=20)
            out.append((cid, x.status_code, x.text.count("BEGIN:VEVENT"), (re.search(r"X-WR-CALNAME:(.*)", x.text) or [None, ""])[1].strip()))
    except Exception as e:
        out.append(str(e)[:80])
    return out
with cf.ThreadPoolExecutor(10) as ex:
    for res in ex.map(check, HOSTS): print(*res, flush=True)
