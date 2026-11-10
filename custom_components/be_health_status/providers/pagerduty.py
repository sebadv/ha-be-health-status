"""PagerDuty-hosted status pages (e.g. CareConnect / Corilus).

These pages render in the browser from three small JSON endpoints:
``/api/services`` (all services), ``/api/impacted_services`` (services with an
open incident or maintenance, each with an ``impact_severity_id``) and
``/api/post_enums`` (what each severity id means).
"""

from __future__ import annotations

from typing import Any

import aiohttp

from ..models import Component, Snapshot, Status, worst
from .base import Provider, ProviderError, get_json

# layout_settings.key of an "impacts" post enum -> Status
_IMPACT_KEYS: dict[str, Status] = {
    "incident/impacts/operational": Status.OPERATIONAL,
    "incident/impacts/degraded": Status.DEGRADED,
    "incident/impacts/degraded_performance": Status.DEGRADED,
    "incident/impacts/partial_outage": Status.PARTIAL_OUTAGE,
    "incident/impacts/outage": Status.MAJOR_OUTAGE,
    "incident/impacts/major_outage": Status.MAJOR_OUTAGE,
    "maintenance/impacts/operational": Status.OPERATIONAL,
    "maintenance/impacts/maintenance": Status.MAINTENANCE,
}


def _status_for_enum(enum: dict[str, Any] | None) -> tuple[Status, str | None]:
    """Status and readable label for an impact severity enum."""
    if not enum:
        # An impact we cannot interpret is still an impact.
        return Status.DEGRADED, None
    key = (enum.get("layout_settings") or {}).get("key", "")
    label = enum.get("description") or enum.get("name")
    if key in _IMPACT_KEYS:
        return _IMPACT_KEYS[key], label
    text = f"{key} {label or ''}".lower()
    if "maintenance" in text:
        return Status.MAINTENANCE, label
    if "partial" in text:
        return Status.PARTIAL_OUTAGE, label
    if "outage" in text:
        return Status.MAJOR_OUTAGE, label
    if "operational" in text:
        return Status.OPERATIONAL, label
    return Status.DEGRADED, label


def parse_pagerduty(services: Any, impacted: Any, post_enums: Any) -> Snapshot:
    """Combine the three endpoints into a Snapshot."""
    try:
        service_rows = services["services"]
        impact_rows = impacted.get("impacted_services", []) or []
        enum_rows = post_enums.get("post_enums", []) or []
    except (KeyError, TypeError, AttributeError) as err:
        raise ProviderError("status page answered with an unexpected format") from err

    enums = {e.get("id"): e for e in enum_rows if isinstance(e, dict)}
    impacts: dict[str, list[tuple[Status, str | None]]] = {}
    for row in impact_rows:
        sid = row.get("service_id")
        if sid:
            impacts.setdefault(sid, []).append(_status_for_enum(enums.get(row.get("impact_severity_id"))))

    components: dict[str, Component] = {}
    for row in service_rows:
        sid = row.get("id")
        if not sid or row.get("is_active") is False:
            continue
        found = impacts.get(sid, [])
        status = worst([s for s, _ in found]) if found else Status.OPERATIONAL
        label = next((lbl for s, lbl in found if s == status and lbl), None)
        components[sid] = Component(
            id=sid,
            name=row.get("display_name") or row.get("name") or sid,
            status=status,
            raw_status=label or ("operational" if status == Status.OPERATIONAL else None),
        )
    if not components:
        raise ProviderError("status page lists no services")
    return Snapshot(components=components)


class PagerDutyProvider(Provider):
    """Any status page hosted by PagerDuty."""

    type = "pagerduty"
    fields = (("url", "url", None),)

    @property
    def base_url(self) -> str:
        return str(self.params["url"]).rstrip("/")

    @property
    def title(self) -> str:
        return self.params.get("name") or self.base_url.split("//", 1)[-1]

    @property
    def unique_id(self) -> str:
        return f"pagerduty_{self.base_url.split('//', 1)[-1].lower()}"

    @property
    def url(self) -> str:
        return self.base_url

    async def async_fetch(self, session: aiohttp.ClientSession) -> Snapshot:
        services = await get_json(session, f"{self.base_url}/api/services")
        impacted = await get_json(session, f"{self.base_url}/api/impacted_services")
        enums = await get_json(session, f"{self.base_url}/api/post_enums")
        return parse_pagerduty(services, impacted, enums)
