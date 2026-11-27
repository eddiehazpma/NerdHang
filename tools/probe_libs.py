"""Find LibraryMarket / LibCal calendars for Long Island libraries."""
import re, requests, concurrent.futures as cf
UA = {"User-Agent": "Mozilla/5.0 (compatible; NerdHang-event-calendar/0.1; +https://github.com/eddiehazpma/NerdHang)"}
LIBS = """baldwin bellmore northbellmore bethpage bayville merrick northmerrick eastmeadow eastrockaway elmont floralpark
franklinsquare freeport gardencity glencove goldcoast greatneck hempstead hewlettwoodmere hwpl hicksville islandpark
islandtrees jericho lakeview locustvalley lynbrook malverne oceanside oysterbay peninsula plainedge ppl plainview
pobpl rockvillecentre rvc roosevelt bryant roslyn seaford seacliff shelterrock uniondale valleystream waldinger wantagh
westhempstead westbury hillside mineola amagansett babylon bayshore bayportbluepoint southcountry brightwaters
centermoriches centralislip coldspringharbor cshlibrary connetquot copiague cutchogue deerpark easthampton eastmoriches
elwood floyd greenport halfhollowhills hhhlibrary hamptonbays harborfields hauppauge huntington kingspark longwood
mastic mmsl mattituck middlecountry mcpl montauk northbabylon northport nenpl patchogue pmlib quogue riverhead
rogers southampton sayville shelterisland smithtown southhuntington shpl southold westbabylon westislip westhampton
wyandanch hamptonlibrary johnjermain sagharbor swr shorehamwadingriver nbpl wbpl wipl bslib cplib""".split()
def variants(s):
    yield f"https://{s}.librarycalendar.com/events/feed/ical"
    for suf in ("pl", "library", "publiclibrary"):
        yield f"https://{s}{suf}.librarycalendar.com/events/feed/ical"
    for dom in (f"{s}library.org", f"{s}pl.org", f"{s}publiclibrary.org", f"{s}library.info", f"{s}.suffolk.lib.ny.us", f"{s}.nassaulibrary.org"):
        yield f"https://www.{dom}/events/feed/ical"
    yield f"https://{s}.libcal.com/calendar"
    for suf in ("pl", "library"):
        yield f"https://{s}{suf}.libcal.com/calendar"
def check(url):
    try:
        r = requests.get(url, headers=UA, timeout=15, allow_redirects=True)
    except Exception:
        return None
    if r.status_code != 200: return None
    b = r.text
    if b.lstrip().startswith("BEGIN:VCALENDAR"):
        name = (re.search(r"X-WR-CALNAME:(.*)", b) or [None, ""])[1].strip()
        return ("ICS", url, b.count("BEGIN:VEVENT"), name)
    if "libcal.com" in url and "libcal" in b.lower():
        cids = sorted(set(re.findall(r"cid=(\d+)", b)))
        title = (re.search(r"<title>(.*?)</title>", b, re.S) or [None, ""])[1].strip()[:80]
        return ("LIBCAL", r.url, cids[:6], title)
    return None
urls = [u for s in LIBS for u in variants(s)]
found = {}
with cf.ThreadPoolExecutor(24) as ex:
    for res in ex.map(check, urls):
        if res: print(*res, flush=True)
