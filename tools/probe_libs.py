import re, json, requests, concurrent.futures as cf
UA = {"User-Agent": "Mozilla/5.0 (compatible; NerdHang-event-calendar/0.1; +https://github.com/eddiehazpma/NerdHang)", "X-Requested-With": "XMLHttpRequest"}
HOSTS = """bryantlibrary eastmeadow elmontlibrary floralparklibrary franklinsquarepl freeportlibrary gardencitypl glencovelibrary
hempsteadlibrary hicksvillelibrary hillsidelibrary huntingtonlibrary hwpl islandparklibrary johnjermain
lakeviewlibrary longwood northbellmorelibrary oceansidelibrary plainedgelibrary rvcpl seaclifflibrary wantaghlibrary westburylibrary""".split()
def check(h):
    out = [h]
    try:
        x = requests.get(f"https://{h}.libcal.com/ical_subscribe.php?src=p&cid=-1", headers=UA, timeout=20)
        out.append(("cid-1", x.status_code, x.text.count("BEGIN:VEVENT")))
        r = requests.get(f"https://{h}.libcal.com/ajax/calendar/list", params={"c": -1, "date": "0000-00-00", "perpage": 48, "page": 1, "audience": "", "cats": "", "camps": "", "inc": 0}, headers=UA, timeout=20)
        try:
            j = r.json()
            res = j.get("results", [])
            cids = sorted({str(e.get("calendar_id") or e.get("cid") or "") for e in res})
            out.append(("ajax", r.status_code, j.get("total_results"), cids[:5], [e.get("title") for e in res[:3]], list(res[0].keys())[:25] if res else None))
            for cid in [c for c in cids if c][:3]:
                y = requests.get(f"https://{h}.libcal.com/ical_subscribe.php?src=p&cid={cid}", headers=UA, timeout=20)
                out.append((cid, y.status_code, y.text.count("BEGIN:VEVENT")))
        except ValueError:
            out.append(("ajax", r.status_code, r.text[:120]))
    except Exception as e:
        out.append(str(e)[:80])
    return out
with cf.ThreadPoolExecutor(6) as ex:
    for res in ex.map(check, HOSTS): print(*res, flush=True)
