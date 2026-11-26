"""Keyword filtering for general-purpose calendars."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

from .models import Event

KEYWORDS = Path(__file__).resolve().parent / "keywords.yaml"


def _compile(words: list[str]) -> re.Pattern:
    return re.compile(r"\b(?:" + "|".join(f"(?:{w})" for w in words) + r")\b", re.I)


@lru_cache(maxsize=None)
def _rules(path: str = str(KEYWORDS)):
    data = yaml.safe_load(Path(path).read_text())
    cats = [(cat, _compile(words)) for cat, words in data["categories"].items()]
    exclude = _compile(data.get("exclude") or ["(?!x)x"])
    return cats, exclude


def classify(title: str, description: str = "") -> str | None:
    """Return the category for an event, or None if it isn't a NerdHang event.
    The title counts first, so a museum talk titled "Model Trains" is trains."""
    cats, exclude = _rules()
    for text in (title, f"{title} {description}"):
        if exclude.search(title):
            return None
        for cat, pattern in cats:
            if pattern.search(text):
                return cat
    return None


def filter_events(events: list[Event], source: dict) -> list[Event]:
    """Apply the source's `filter: keywords` / `category: auto` settings."""
    keep = []
    for e in events:
        cat = classify(e.title, e.description)
        if source.get("filter") == "keywords" and cat is None:
            continue
        if source.get("category") == "auto":
            e.category = cat or "other"
        keep.append(e)
    return keep
