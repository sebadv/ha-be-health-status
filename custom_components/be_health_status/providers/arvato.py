"""NMVS availability as monitored by Arvato Systems (status-nmvs.arvato-systems.de).

Arvato runs the National Medicines Verification Systems of Belgium/Luxembourg
and several other countries. Its status page reads ``/api/services``: one
service group per country, each with ws-* and api-cer* endpoint services.
"""

from __future__ import annotations

from typing import Any

import aiohttp

from ..models import Component, Snapshot, Status
from .base import Provider, ProviderError, get_json

BASE_URL = "https://status-nmvs.arvato-systems.de"

# Codes from the page's own legend.
_CODES: dict[int, Status] = {
    0: Status.OPERATIONAL,  # Available
    1: Status.DEGRADED,  # Available, but degraded
    2: Status.MAJOR_OUTAGE,  # Unavailable
    3: Status.UNKNOWN,  # Unknown / No Data
}


def _status(item: dict[str, Any]) -> tuple[Status, str | None]:
    latest = item.get("latestStatus") or {}
    status = _CODES.get(latest.get("status"), Status.UNKNOWN)
    # The monitor flags stale data itself; do not report an old "Available".
    if item.get("outdated"):
        status = Status.UNKNOWN
    return status, latest.get("statusDescription")


def parse_arvato(payload: Any) -> Snapshot:
    """Turn /api/services into a Snapshot: one component per country and per endpoint."""
    try:
        groups = payload["serviceGroups"]
    except (KeyError, TypeError) as err:
        raise ProviderError("Arvato answered with an unexpected format") from err

    components: dict[str, Component] = {}
    for group in groups:
        gkey, gname = group.get("key"), group.get("name")
        if not gkey or not gname:
            continue
        status, raw = _status(group)
        components[gkey] = Component(
            id=gkey,
            name=f"NMVS {gname}",
            status=status,
            raw_status=raw,
            is_group=True,
            last_updated=(group.get("latestStatus") or {}).get("timestamp"),
            extra={"description": group.get("description")},
        )
        for svc in group.get("services") or []:
            skey = svc.get("key")
            if not skey:
                continue
            status, raw = _status(svc)
            components[skey] = Component(
                id=skey,
                name=f"NMVS {gname} {svc.get('name') or skey}",
                status=status,
                raw_status=raw,
                group=f"NMVS {gname}",
                last_updated=svc.get("lastUpdated"),
                extra={"description": svc.get("description")},
            )
    if not components:
        raise ProviderError("Arvato lists no countries")
    return Snapshot(components=components, title="NMVS (Arvato)")


class ArvatoProvider(Provider):
    """NMVS status by Arvato Systems."""

    type = "arvato_nmvs"

    @property
    def title(self) -> str:
        return "NMVS"

    @property
    def unique_id(self) -> str:
        return "arvato_nmvs"

    @property
    def url(self) -> str:
        return f"{BASE_URL}/#/group/belgium-sg"

    async def async_fetch(self, session: aiohttp.ClientSession) -> Snapshot:
        return parse_arvato(await get_json(session, f"{BASE_URL}/api/services"))
