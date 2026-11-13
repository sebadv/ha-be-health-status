"""Interventions (planned maintenance) and incidents from www.status.ehealth.fgov.be.

- Interventions: the home page carries the whole intervention calendar as JSON
  in ``<body data-interventions="...">``. Partners other than eHealth (CIN-NIC
  for MyCareNet, Smals, Vitalink, ...) publish theirs there too.
- Incidents: the official RSS feed; each title ends in ``|<status>``. New
  incidents start as "Investigating" and end as "Solved".

Both change rarely, so they are fetched at most every ``EVENTS_TTL`` and shared
between providers.
"""

from __future__ import annotations

import html
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from ..models import Event
from .base import ProviderError, get_text, parse_datetime
from .htmltree import parse_html

SITE = "https://www.status.ehealth.fgov.be"
TZ = ZoneInfo("Europe/Brussels")
EVENTS_TTL = 600  # seconds; the default, the user can change it under Configure
#: An incident not marked solved after this long is assumed forgotten, not ongoing.
INCIDENT_MAX_AGE = timedelta(days=7)
_CLOSED_STATES = {"solved", "resolved", "closed", "opgelost", "résolu"}

_PERIOD = re.compile(r"(\d{2}/\d{2}/\d{2})\s+(\d{1,2}:\d{2})\s*-\s*(?:(\d{2}/\d{2}/\d{2})\s+)?(\d{1,2}:\d{2})")


def html_to_text(value: Any) -> str | None:
    """Plain text from the small HTML snippets the site uses; list items joined by '; '."""
    if not value or not isinstance(value, str):
        return None
    text = re.sub(r"(?i)<br\s*/?>|</p>|</li>", "; ", value)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    parts = [" ".join(p.split()) for p in text.split(";")]
    return "; ".join(p for p in parts if p) or None


def _local(day: str, clock: str) -> datetime | None:
    try:
        return datetime.strptime(f"{day} {clock}", "%d/%m/%y %H:%M").replace(tzinfo=TZ)
    except ValueError:
        return None


def _period(item: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    """Start and end from "14/11/26 20:00 - 23:00" or "04/11/26 06:00 - 12/11/26 23:00"."""
    match = _PERIOD.search(item.get("period") or "")
    if match:
        start_day, start_clock, end_day, end_clock = match.groups()
        start = _local(start_day, start_clock)
        end = _local(end_day or start_day, end_clock)
        if start and end and end < start:  # crosses midnight
            end += timedelta(days=1)
        return start, end
    start = parse_datetime(item.get("sortDate"))
    if start and start.tzinfo is None:
        start = start.replace(tzinfo=TZ)
    end = parse_datetime(item.get("end"))
    if end and end.tzinfo is None:
        end = end.replace(tzinfo=TZ)
    return start, end


def parse_interventions(page: str, partners: set[str] | None = None) -> list[Event]:
    """Open interventions from the home page, optionally only those of some partners."""
    root = parse_html(page)
    body = root.find("body")
    raw = body.attrs.get("data-interventions") if body else None
    if not raw:
        raise ProviderError("eHealth home page has no intervention calendar")
    try:
        items = json.loads(raw)
    except ValueError as err:
        raise ProviderError("eHealth intervention calendar is not valid JSON") from err

    events: list[Event] = []
    for item in items if isinstance(items, list) else []:
        if item.get("closed"):
            continue
        partner = item.get("provider")
        if partners is not None and partner not in partners:
            continue
        start, end = _period(item)
        impact_label = (item.get("business_impact") or "").strip().lower()
        url = item.get("url")
        events.append(
            Event(
                id=str(item.get("id")),
                name=(item.get("title") or "").strip(),
                kind="maintenance",
                status="planned",
                impact=item.get("business_impact"),
                url=f"{SITE}{url}" if isinstance(url, str) and url.startswith("/") else url,
                starts_at=start,
                ends_at=end,
                business_impact=(False if impact_label.startswith("no ") else True if impact_label else None),
                details={
                    "partner": partner,
                    "type": (item.get("type") or "").replace("type.", "") or None,
                    "scope": html_to_text(item.get("scope")),
                    "impact": html_to_text(item.get("impact")),
                },
            )
        )
    return events


def parse_incidents(rss: str, now: datetime) -> list[Event]:
    """Incidents from the RSS feed that are not solved yet."""
    try:
        root = ET.fromstring(rss)
    except ET.ParseError as err:
        raise ProviderError("eHealth RSS feed is not valid XML") from err

    events: list[Event] = []
    for item in root.iter("item"):
        if (item.findtext("category") or "incident").strip().lower() != "incident":
            continue
        title = (item.findtext("title") or "").strip()
        name, _, status = title.rpartition("|")
        if not name:
            name, status = status, ""
        if status.strip().lower() in _CLOSED_STATES:
            continue
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
        except (TypeError, ValueError):
            published = None
        if published and now - published > INCIDENT_MAX_AGE:
            continue
        link = (item.findtext("link") or "").strip() or None
        events.append(
            Event(
                id=link or title,
                name=name.strip(),
                kind="incident",
                status=status.strip() or None,
                url=link,
                starts_at=published,
                details={"description": html_to_text(item.findtext("description"))},
            )
        )
    return events


_cache: dict[str, tuple[float, Any]] = {}


async def _cached_text(session: aiohttp.ClientSession, url: str, ttl: float) -> str:
    hit = _cache.get(url)
    if hit and time.monotonic() - hit[0] < ttl:
        return hit[1]
    text = await get_text(session, url)
    _cache[url] = (time.monotonic(), text)
    return text


async def async_fetch_events(
    session: aiohttp.ClientSession,
    lang: str,
    *,
    partners: set[str] | None = None,
    incidents: bool = True,
    ttl: float = EVENTS_TTL,
) -> list[Event]:
    """Interventions (and incidents) for one language. Raises ProviderError on failure."""
    lang = "fr" if lang == "fr" else "nl"
    events = parse_interventions(await _cached_text(session, f"{SITE}/{lang}", ttl), partners)
    if incidents:
        rss = await _cached_text(session, f"{SITE}/{lang}/rss.xml", ttl)
        events += parse_incidents(rss, datetime.now(TZ))
    return events
