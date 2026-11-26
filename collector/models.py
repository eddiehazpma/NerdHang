"""The common event shape every source is converted into."""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class Location:
    name: str = ""
    address: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None

    @property
    def has_coords(self) -> bool:
        return self.lat is not None and self.lon is not None

    def geocode_query(self) -> str:
        return self.address or self.name


@dataclass
class Event:
    source_id: str
    source_uid: str
    title: str
    # all_day events use date objects (end is inclusive); timed events use
    # timezone-aware datetimes.
    start: date | datetime
    end: date | datetime
    all_day: bool
    category: str
    location: Location = field(default_factory=Location)
    url: str = ""
    description: str = ""
    source_name: str = ""

    @property
    def id(self) -> str:
        raw = f"{self.source_id}:{self.source_uid}".encode()
        return hashlib.sha1(raw).hexdigest()[:16]

    @property
    def start_date(self) -> date:
        return self.start if not isinstance(self.start, datetime) else self.start.date()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id
        d["start"] = self.start.isoformat()
        d["end"] = self.end.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        def parse(v: str, all_day: bool):
            return date.fromisoformat(v) if all_day else datetime.fromisoformat(v)

        d = dict(d)
        d.pop("id", None)
        d["location"] = Location(**d.get("location") or {})
        d["start"] = parse(d["start"], d["all_day"])
        d["end"] = parse(d["end"], d["all_day"])
        return cls(**d)
