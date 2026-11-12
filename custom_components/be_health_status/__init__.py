"""BE Health Status: status of Belgian healthcare and e-government services."""

from __future__ import annotations

import asyncio

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import CONF_COMPONENTS, CONF_SECTORS, CONF_SOURCES, CONF_TOPICS, DOMAIN
from .coordinator import HealthStatusConfigEntry, SourceCoordinator, SourceRuntime

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: HealthStatusConfigEntry) -> bool:
    """Start one coordinator per source.

    A source that does not answer does not block the others: its entities
    are unavailable until it answers again.
    """
    sources = entry.options.get(CONF_SOURCES, {})
    components = entry.options.get(CONF_COMPONENTS, {})
    runtime: dict[str, SourceRuntime] = {}
    for key, source in sources.items():
        runtime[key] = SourceRuntime(
            key=key,
            title=source.get("title", key),
            coordinator=SourceCoordinator(hass, entry, key, source),
            components=dict(components.get(key, {})),
        )
    await asyncio.gather(*(r.coordinator.async_refresh() for r in runtime.values()))
    if runtime and not any(r.coordinator.last_update_success for r in runtime.values()):
        # Nothing answered at all: most likely no internet. Let Home Assistant retry.
        raise ConfigEntryNotReady(
            "; ".join(f"{r.title}: {r.coordinator.last_exception}" for r in runtime.values())
        )
    entry.runtime_data = runtime

    # Remove devices of sources that are no longer followed.
    device_registry = dr.async_get(hass)
    wanted = {(DOMAIN, f"{entry.entry_id}_{key}") for key in runtime}
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if not device.identifiers & wanted:
            device_registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: HealthStatusConfigEntry) -> bool:
    """Convert a 0.1.0 entry (one source per entry) to the current layout."""
    if entry.version == 1:
        provider = entry.data.get("provider")
        params = dict(entry.data.get("params", {}))
        key = {
            "ehealth": "ehealth",
            "pagerduty": "careconnect",
            "statuspage": "itsme",
            "arvato_nmvs": "nmvs",
            "ibz": "rijksregister",
        }.get(provider or "", f"mycarenet_{params.get('sector', 'pharma')}")
        topic = "mycarenet" if key.startswith("mycarenet") else key
        options = {
            CONF_TOPICS: [topic],
            CONF_SECTORS: [params.get("sector", "pharma")],
            CONF_SOURCES: {key: {"provider": provider, "params": params, "title": entry.title}},
            # 0.1.0 stored only ids; names come back on the next "Configure".
            CONF_COMPONENTS: {key: {cid: cid for cid in entry.options.get(CONF_COMPONENTS, [])}},
        }
        hass.config_entries.async_update_entry(entry, data={}, options=options, version=2)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HealthStatusConfigEntry) -> bool:
    """Unload."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
