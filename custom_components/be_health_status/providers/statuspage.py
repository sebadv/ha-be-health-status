"""Atlassian Statuspage pages (e.g. itsme) via the public ``/api/v2/summary.json``."""

from __future__ import annotations

from typing import Any

import aiohttp

from ..models import Component, Event, Snapshot, Status
from .base import Provider, ProviderError, get_json, parse_datetime

_STATUS: dict[str, Status] = {
    "operational": Status.OPERATIONAL,
    "degraded_performance": Status.DEGRADED,
    "partial_outage": Status.PARTIAL_OUTAGE,
    "major_outage": Status.MAJOR_OUTAGE,
    "under_maintenance": Status.MAINTENANCE,
}

# Incident/maintenance states that are over and should not be reported.
_CLOSED = {"resolved", "postmortem", "completed"}


def _event(item: dict[str, Any], kind: str) -> Event:
    return Event(
        id=str(item.get("id")),
        name=item.get("name") or "",
        kind=kind,
        status=item.get("status"),
        impact=item.get("impact"),
        url=item.get("shortlink"),
        starts_at=parse_datetime(item.get("scheduled_for") or item.get("started_at")),
        ends_at=parse_datetime(item.get("scheduled_until") or item.get("resolved_at")),
        component_ids=[c.get("id") for c in item.get("components") or [] if c.get("id")],
    )


def parse_statuspage(summary: Any) -> Snapshot:
    """Turn summary.json into a Snapshot."""
    try:
        rows = summary["components"]
    except (KeyError, TypeError) as err:
        raise ProviderError("not a Statuspage summary.json") from err

    groups = {r["id"]: r.get("name") for r in rows if r.get("group") and r.get("id")}
    components: dict[str, Component] = {}
    for row in rows:
        cid = row.get("id")
        if not cid:
            continue
        raw = row.get("status")
        components[cid] = Component(
            id=cid,
            name=row.get("name") or cid,
            status=_STATUS.get(raw or "", Status.UNKNOWN),
            raw_status=raw,
            group=groups.get(row.get("group_id")),
            is_group=bool(row.get("group")),
            last_updated=row.get("updated_at"),
            position=row.get("position") if isinstance(row.get("position"), int) else None,
        )

    events = [
        _event(i, "incident") for i in summary.get("incidents") or [] if i.get("status") not in _CLOSED
    ] + [
        _event(m, "maintenance")
        for m in summary.get("scheduled_maintenances") or []
        if m.get("status") not in _CLOSED
    ]
    if not components:
        raise ProviderError("status page lists no components")
    title = (summary.get("page") or {}).get("name")
    return Snapshot(components=components, events=events, title=title)


class StatuspageProvider(Provider):
    """Any page hosted by Atlassian Statuspage."""

    type = "statuspage"
    fields = (("url", "url", None),)

    @property
    def base_url(self) -> str:
        return str(self.params["url"]).rstrip("/")

    @property
    def title(self) -> str:
        return self.params.get("name") or self.base_url.split("//", 1)[-1]

    @property
    def unique_id(self) -> str:
        return f"statuspage_{self.base_url.split('//', 1)[-1].lower()}"

    @property
    def url(self) -> str:
        return self.base_url

    async def async_fetch(self, session: aiohttp.ClientSession) -> Snapshot:
        return parse_statuspage(await get_json(session, f"{self.base_url}/api/v2/summary.json"))
