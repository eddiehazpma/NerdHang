"""Turn addresses into map coordinates, with a cache so each place is looked
up only once. Uses OpenStreetMap's free Nominatim service, which allows at
most one request per second and asks for a descriptive User-Agent."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Callable, Optional

import requests

USER_AGENT = "NerdHang-event-calendar/0.1 (+https://github.com/eddiehazpma/NerdHang)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"

Coords = Optional[tuple[float, float]]


def nominatim_lookup(query: str) -> Coords:
    resp = requests.get(
        NOMINATIM,
        params={"q": query, "format": "json", "limit": 1, "countrycodes": "us,ca"},
        headers={"User-Agent": USER_AGENT},
        timeout=20,
    )
    resp.raise_for_status()
    hits = resp.json()
    time.sleep(1.1)  # Nominatim usage policy: max 1 request per second.
    if not hits:
        return None
    return float(hits[0]["lat"]), float(hits[0]["lon"])


_COUNTRY = re.compile(r",?\s*(united states( of america)?|usa)\s*$", re.I)


def query_variants(query: str) -> list[str]:
    q = _COUNTRY.sub("", " ".join(query.split())).strip(" ,")
    parts = [p.strip() for p in q.split(",") if p.strip()]
    variants = [q]
    if len(parts) >= 3:
        variants.append(", ".join(parts[1:]))   # drop the venue name
    if len(parts) >= 2:
        variants.append(", ".join(parts[-3:] if len(parts) >= 4 else parts[-2:]))  # town, state, ZIP
    seen, out = set(), []
    for v in variants:
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return out


class Geocoder:
    def __init__(self, cache_path: Path, lookup: Callable[[str], Coords] = nominatim_lookup, max_lookups: int = 200):
        self.cache_path = cache_path
        self.lookup = lookup
        self.max_lookups = max_lookups
        self.lookups = 0
        self.cache: dict[str, Optional[list[float]]] = (
            json.loads(cache_path.read_text()) if cache_path.exists() else {}
        )

    def __call__(self, query: str) -> Coords:
        """Try the full address, then without the venue name, then just the
        town/state/ZIP. OpenStreetMap often doesn't know a hall's name."""
        for variant in query_variants(query):
            coords = self._lookup_one(variant)
            if coords:
                return coords
        return None

    def _lookup_one(self, query: str) -> Coords:
        key = " ".join(query.lower().split())
        if not key:
            return None
        if key in self.cache:
            hit = self.cache[key]
            return tuple(hit) if hit else None
        if self.lookups >= self.max_lookups:
            return None  # try again on the next run
        self.lookups += 1
        try:
            coords = self.lookup(query)
        except requests.RequestException as exc:
            print(f"  geocode failed for {query!r}: {exc}")
            return None  # not cached, so it is retried next run
        self.cache[key] = list(coords) if coords else None
        return coords

    def save(self) -> None:
        self.cache_path.write_text(json.dumps(self.cache, indent=1, sort_keys=True) + "\n")
