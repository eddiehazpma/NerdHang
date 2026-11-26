# NerdHang

A free public calendar of train shows, ham radio hamfests, computer shows, special train displays and museum events, filtered to what's near you.

## How it works

1. **Collector** (`collector/`): a Python program that runs every morning on GitHub Actions. It reads each source in `collector/sources.yaml`, converts events into one common format, looks up map coordinates (OpenStreetMap, cached in `data/geocache.json`), removes duplicates and writes:
   - `data/events.json`: every upcoming event, used by the website.
   - `data/nerdhang.ics`: the same events as a calendar feed you can subscribe to.
2. **Website** (`site/`): a static page with list and month-calendar views. It uses the browser's location (or a town/ZIP you type) to show events within a chosen distance, filters by category, and lets you download the shown events as .ics, add single events to Google Calendar, or subscribe to the full feed. It is published to GitHub Pages by the same daily workflow.

If a source's site is down, the collector keeps that source's events from the previous run and carries on with the rest.

## Adding a source

- **Calendar feed (.ics):** copy an entry in `collector/sources.yaml`, change the `id`, `name`, `url` and `category`. That's it.
- **One-off event or a site with no feed:** add it to `collector/manual_events.yaml`.
- Research notes on candidate sources are in `docs/sources.md`.

## Running it yourself

```
pip install -r requirements.txt
python -m pytest -q            # tests
python -m collector.build      # collect events into data/
```

To preview the website locally:

```
mkdir -p /tmp/nh && cp -r site/. data/events.json data/nerdhang.ics /tmp/nh/ && python -m http.server -d /tmp/nh 8000
```

then open http://localhost:8000.

To run it on GitHub without waiting for the morning: Actions tab → "Collect events" → "Run workflow".
