"""MyCareNet availability from the intermutualistic dashboard (dashboard.intermut.be).

The dashboard is a server-rendered page per sector with one table per
transaction type. Each row's cell carries a Bootstrap alert class for its colour.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


import aiohttp

from ..models import Component, Snapshot, Status, worst
from .base import Provider, ProviderError, get_text
from .ehealth_events import async_fetch_events
from .htmltree import Node, parse_html

BASE_URL = "https://dashboard.intermut.be/"
SECTORS = ("pharma", "doctors", "dentists", "nurses")

_ALERTS = {
    "alert-success": Status.OPERATIONAL,
    "alert-warning": Status.DEGRADED,
    "alert-danger": Status.MAJOR_OUTAGE,
    "alert-info": Status.MAINTENANCE,
}


def _lang_part(text: str, lang: str) -> str:
    """Pick the Dutch or French half of an "NL / FR" label."""
    parts = re.split(r"\s*/\s*", text, maxsplit=1)
    if len(parts) == 2 and parts[0] and parts[1]:
        return parts[1] if lang == "fr" else parts[0]
    return text


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _status(cell: Node) -> Status:
    return next((s for c, s in _ALERTS.items() if c in cell.classes), Status.UNKNOWN)


def parse_intermut(html: str, lang: str = "nl") -> Snapshot:
    """Read every table row that has a status cell, plus one component per table."""
    root = parse_html(html)
    container = root.find(cls="container-fluid") or root
    components: dict[str, Component] = {}

    for table in container.find_all("table"):
        head = table.find("thead")
        section_full = head.text() if head else ""
        if not section_full:
            continue
        section_id = _slug(_lang_part(section_full, "nl"))
        section = _lang_part(section_full, lang)
        members: list[Component] = []
        for row in table.find_all("tr"):
            label_cell, value_cell = row.find("th"), row.find("td")
            if label_cell is None or value_cell is None or head is not None and row.parent is head:
                continue
            label_full = label_cell.text()
            comp = Component(
                id=f"{section_id}__{_slug(_lang_part(label_full, 'nl'))}",
                name=f"{section} – {_lang_part(label_full, lang)}",
                status=_status(value_cell),
                raw_status=_lang_part(value_cell.text(), lang) or None,
                group=section,
            )
            components[comp.id] = comp
            members.append(comp)
        if members:
            overall = worst([m.status for m in members])
            components[section_id] = Component(
                id=section_id,
                name=section,
                status=overall,
                raw_status=next(m.raw_status for m in members if m.status == overall),
                is_group=True,
                extra={"members": [m.name for m in members]},
            )
    if not components:
        raise ProviderError("MyCareNet dashboard shows no services for this sector")
    return Snapshot(components=components)


class IntermutProvider(Provider):
    """MyCareNet (intermutualistisch dashboard), one sector."""

    type = "intermut"
    has_maintenance = True

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(params)
        self._last_events: list = []

    @property
    def sector(self) -> str:
        sector = self.params.get("sector", "pharma")
        return sector if sector in SECTORS else "pharma"

    @property
    def lang(self) -> str:
        return "fr" if self.params.get("language") == "fr" else "nl"

    @property
    def url(self) -> str:
        return f"{BASE_URL}?sector={self.sector}&partners=yes"

    async def async_fetch(self, session: aiohttp.ClientSession) -> Snapshot:
        snapshot = parse_intermut(await get_text(session, self.url), self.lang)
        try:
            # MyCareNet (CIN-NIC) announces its maintenance on the eHealth status site.
            snapshot.events = await async_fetch_events(
                session, self.lang, partners={"CIN-NIC"}, incidents=False, ttl=self.events_ttl
            )
        except ProviderError:
            snapshot.events = self._last_events
        self._last_events = snapshot.events
        return snapshot
