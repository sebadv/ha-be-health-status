"""eHealth platform (status.ehealth.fgov.be) via its public JSON API."""

from __future__ import annotations

import logging
import re
from typing import Any

import aiohttp

from ..models import Component, Snapshot, Status, worst
from .base import Provider, ProviderError, get_json
from .ehealth_events import async_fetch_events

_LOGGER = logging.getLogger(__name__)

API_URL = "https://status.ehealth.fgov.be/{lang}/api/components/prod"
PAGE_URL = "https://status.ehealth.fgov.be/{lang}/dashboard"

# The API returns a localised status_name and a numeric status_code. Only code 1
# (operational) has been observed; other codes are mapped from the localised
# text, which also covers wording changes on their side.
_KEYWORDS: tuple[tuple[Status, tuple[str, ...]], ...] = (
    (Status.MAINTENANCE, ("onderhoud", "maintenance", "wartung")),
    (Status.PARTIAL_OUTAGE, ("gedeeltelijk", "partiel", "partial")),
    (
        Status.MAJOR_OUTAGE,
        ("onderbreking", "storing", "niet beschikbaar", "onbeschikbaar", "indisponible",
         "interruption", "panne", "outage", "unavailable"),
    ),
    (Status.DEGRADED, ("verminder", "verstoor", "dégrad", "degrad", "perturb", "trage", "lent")),
    (Status.OPERATIONAL, ("operation", "opération", "beschikbaar", "disponible", "ok")),
)


def status_from_ehealth(code: Any, name: str | None) -> Status:
    """Map eHealth's status_code / status_name to a normalised Status."""
    text = (name or "").strip().lower()
    for status, words in _KEYWORDS:
        if any(word in text for word in words):
            return status
    if code == 1:
        return Status.OPERATIONAL
    return Status.UNKNOWN


def short_group_name(name: str) -> tuple[str, int | None]:
    """"9. Services for … - MetaHub, Consent & …" -> ("MetaHub, Consent & …", 9).

    The page numbers its groups and adds a long explanation after " - "; keep
    the shortest part (usually the service's own name) and the number for sorting.
    """
    match = re.match(r"\s*(\d+)\.\s*(.*)", name)
    number = int(match.group(1)) if match else None
    rest = (match.group(2) if match else name).strip()
    parts = [p.strip() for p in rest.split(" - ") if p.strip()]
    short = min(parts, key=len) if parts else rest
    # "UPPAD (Unique Portal for …)" -> "UPPAD"
    paren = re.match(r"^(\S{2,12}) \((.{15,})\)$", short)
    if paren:
        short = paren.group(1)
    return short, number


def group_component_id(group_id: str) -> str:
    """Component id used for a whole eHealth group."""
    return f"group:{group_id}"


def parse_ehealth(payload: Any, lang: str) -> Snapshot:
    """Turn the components API answer into a Snapshot (services and their groups)."""
    rows = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ProviderError("eHealth answered with an unexpected format")

    name_key = "name_fr" if lang == "fr" else "name_nl"
    group_key = "group_name_fr" if lang == "fr" else "group_name_nl"
    components: dict[str, Component] = {}
    groups: dict[str, list[Component]] = {}
    group_names: dict[str, str] = {}

    for row in rows:
        cid = row.get("id")
        name = row.get(name_key) or row.get("name_nl") or row.get("name_fr")
        if not cid or not name:
            continue
        group_full = row.get(group_key) or row.get("group_name_nl")
        group_name = short_group_name(group_full)[0] if group_full else None
        comp = Component(
            id=str(cid),
            name=str(name).strip(),
            status=status_from_ehealth(row.get("status_code"), row.get("status_name")),
            raw_status=row.get("status_name"),
            group=group_name,
            last_updated=row.get("last_updated"),
            position=row.get("order") if isinstance(row.get("order"), int) else None,
            extra={"status_code": row.get("status_code")},
        )
        components[comp.id] = comp
        if gid := row.get("group_id"):
            groups.setdefault(str(gid), []).append(comp)
            if group_full:
                group_names[str(gid)] = group_full

    for gid, members in groups.items():
        member_worst = worst([m.status for m in members])
        culprit = next((m for m in members if m.status == member_worst), members[0])
        gcid = group_component_id(gid)
        full = group_names.get(gid, gid)
        short, number = short_group_name(full)
        components[gcid] = Component(
            id=gcid,
            name=short,
            status=member_worst,
            raw_status=culprit.raw_status,
            is_group=True,
            last_updated=max((m.last_updated or "" for m in members), default=None) or None,
            position=number,
            extra={"full_name": full, "members": [m.name for m in members]},
        )
    if not components:
        raise ProviderError("eHealth returned no services")
    return Snapshot(components=components)


class EHealthProvider(Provider):
    """status.ehealth.fgov.be."""

    type = "ehealth"
    has_maintenance = True

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(params)
        self._last_events: list = []

    @property
    def lang(self) -> str:
        return "fr" if self.params.get("language") == "fr" else "nl"

    @property
    def url(self) -> str:
        return PAGE_URL.format(lang=self.lang)

    async def async_fetch(self, session: aiohttp.ClientSession) -> Snapshot:
        snapshot = parse_ehealth(await get_json(session, API_URL.format(lang=self.lang)), self.lang)
        try:
            snapshot.events = await async_fetch_events(session, self.lang, ttl=self.events_ttl)
        except ProviderError as err:
            # The service statuses are what matters; keep them when the calendar fails.
            _LOGGER.debug("eHealth interventions/incidents unavailable: %s", err)
            snapshot.events = self._last_events
        self._last_events = snapshot.events
        return snapshot
