# NerdHang event sources (step 1 research)

Researched 2026-11-25. Test area: Long Island, NY. "Feed" means the source publishes a machine-readable calendar we can read without scraping HTML, which is the cheapest, most reliable and most polite option.

## Tier 1: has a calendar feed (start here)

| Source | Covers | How to pull | Notes |
|---|---|---|---|
| Railroad Museum of Long Island (rmli.org) | Riverhead & Greenport museum events, toy train outreach | iCal feed: `https://www.rmli.org/events/?ical=1` | Verified working. 6 events through Dec 13, 2026. Location field is only "NY", so we add the venue ourselves. |
| Train Collectors Association (tcatrains.org) | TCA train meets nationwide | iCal export on event list pages (`.../events/list/?ical=1`) | 31 pages of listings. Feed link exists, contents not yet verified. |
| TCA Eastern Division (easterntca.com) | York Train Fair, PA (the biggest toy train meet in the US) | iCal feed: `https://easterntca.com/future-meet-dates/?ical=1` | Verified. Apr 20-24 and Oct 19-23, 2027. |
| LIMARC (limarc.org) | Long Island ham radio club: hamfests, special event stations | Embedded Google Calendar on its Calendar of Events page, which has a public iCal address | Need to read the calendar ID from the page. |
| Cradle of Aviation Museum (Garden City) | Museum events, astronomy day, STEM festival, Long Island Garden Railway holiday display | iCal link on each event page | Need to find a whole-calendar feed or crawl the event list. |

## Tier 2: good listings, needs page scraping

| Source | Covers | Notes |
|---|---|---|
| ARRL Hamfests & Conventions (arrl.org/hamfests) | Every ARRL-sanctioned hamfest in the US, searchable by ZIP and radius | The single best ham source. No feed. Footer says reproduction without written permission is prohibited, so **ask ARRL for permission** or only store a title, date and link back to them. |
| NMRA events by state (nmra.com/states/new-york) | Model railroad shows, open houses, conventions | 22 pages for NY. State tag is loose (includes NV, ME, Montreal), so we filter by distance. Example: Levittown holiday train layout Dec 4-13, 2026. |
| Model Railroad News Timetable (modelrailroadnews.com/timetable) | National train show list | Plain-text list, ~24 upcoming shows. Sister lists at railfan.com/timetable and rrmodelcraftsman.com/timetable. |
| Vintage Computer Federation (vcfed.org) | VCF East (Wall, NJ, about 2 hours from LI), tech swap meets | VCF East 2027 is Apr 2-4. Few events a year, so they can be checked by hand. |
| eHam.net calendar (eham.net/calendar) | Ham radio events submitted by clubs | Single event pages confirmed; listing page and feed not yet checked. |
| Computer show schedule (community Google Doc) | Vintage computer shows nationwide | Only covers 2026 so far. Useful once the 2027 version appears. |

## Tier 3: worth adding later

- New York Transit Museum (Brooklyn) and its Holiday Train Show at Grand Central.
- Nassau Lionel Operating Engineers open houses (Levittown).
- Oyster Bay Railroad Museum: no online calendar found; events show up in local news and NMRA.
- Long Island Garden Railway Society.
- InfoAge Science History Museums (Wall, NJ).
- Greenberg's / Amherst Railway Society (Springfield, MA) large train shows.
- Hudson Valley train shows (railfan.com listing).
- Family event sites that list train displays (mommypoppins.com Long Island): good for discovery, but we should not copy their content.
- Eventbrite and Meetup: both have search APIs that could pick up computer, maker and retro gaming events.

## What this means for step 2

1. Start with the Tier 1 feeds. They give real Long Island events right away with little code.
2. Add ARRL, NMRA and the timetable lists as scrapers, storing only basic facts (name, date, place, link back), and email ARRL about permission.
3. Let users and organizers submit events. Many small clubs only post on Facebook, so submissions will fill gaps the scrapers miss, and later it doubles as the "featured listing" money option.
4. The collector should run on GitHub Actions, which has open internet access and is free for this size of job.

## Sources you can add

Send any club, museum or show site you know, especially Long Island clubs, and I'll add it to the right tier.

## Added 2026-11-26: town and county calendars, retro gaming, open houses

- **CivicPlus calendar RSS** (`type: civicplus_rss`): Nassau County, Town of Hempstead, Brookhaven, Smithtown, Babylon. Keyword-filtered, so meetings and office closures are dropped.
- **Keywords**: computer/electronics flea markets and swap meets, retro gaming (retro games, classic arcade, pinball, LAN parties, chiptune), and science/tech open houses (labs, BNL, observatories, National Weather Service, lighthouse tours, air shows). Modern gaming nights (Mario Kart, Switch tournaments) and board games are not included.
- **Checked, no usable feed**: LI Herald (calendar widget, no export), Newsday (articles only), News12 Long Island (no feed), theholyblack.com and orderoftheholyblack.com (no events pages), City of Long Beach (events are images and PDFs), North Hempstead, Islip, Oyster Bay (feed empty), Huntington (time.ly, no public export found), Suffolk County (blocks automated requests), BNL and NY State Parks (JavaScript pages). These are candidates for the submit-an-event form.

## Added 2026-11-26: more hobbies

New categories: **Makers & hackers** (makerspaces, 2600 meetings, 3D printing, robotics, model ship and model kit building), **Records & collecting** (record and vinyl fairs, listening clubs, book, paper and ephemera fairs, coin, stamp and comic shows), **Nature & tours** (bird walks, nature walks, geology and mineral clubs, metal detecting, treasure hunts, lighthouse, boat and walking tours, excursions), **Fairs & markets** (farmers markets, Renaissance faires, flea and antique markets). Special train rides (Polar Express, Santa trains, rail excursions) go under Trains. These new categories only match on the event title, and kids'/family events are skipped.

New feeds: South Fork Natural History Museum (SoFo), The Long Island Museum, Old Westbury Gardens, Planting Fields.

Checked, no usable feed: Gregory Museum (school district page), 2600.com meetings (Wix page, no Long Island meeting listed), Theodore Roosevelt Audubon Center, Sands Point Preserve, Long Island Explorium, Long Island Greenbelt hikes, Seatuck, Peconic Land Trust, Fire Island Lighthouse, Vanderbilt Museum (blocks automated requests), LI Maker Space Meetup (no upcoming events), Hamptons Record Fair, Long Island Antiquarian Book & Paper Fair, NY Renaissance Faire (no 2027 dates yet).
