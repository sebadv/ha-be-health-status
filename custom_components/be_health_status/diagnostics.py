"""Diagnostics download: what each source answered, to help debugging."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import HealthStatusConfigEntry


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: HealthStatusConfigEntry) -> dict[str, Any]:
    """Return the settings and the last answer of every source.

    Everything here comes from public status pages; nothing needs redacting.
    """
    sources: dict[str, Any] = {}
    for key, source in entry.runtime_data.items():
        coordinator = source.coordinator
        snapshot = coordinator.data
        sources[key] = {
            "title": source.title,
            "provider": coordinator.provider.type,
            "url": coordinator.provider.url,
            "last_update_success": coordinator.last_update_success,
            "last_exception": repr(coordinator.last_exception) if coordinator.last_exception else None,
            "selected": source.components,
            "snapshot": (
                {
                    "title": snapshot.title,
                    "components": {cid: asdict(c) for cid, c in snapshot.components.items()},
                    "events": [asdict(e) for e in snapshot.events],
                }
                if snapshot
                else None
            ),
        }
    return {"options": dict(entry.options), "sources": sources}
