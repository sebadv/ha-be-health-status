"""BE Health Status: status of Belgian healthcare and e-government services."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import HealthStatusConfigEntry, HealthStatusCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: HealthStatusConfigEntry) -> bool:
    """Set up one status page."""
    coordinator = HealthStatusCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HealthStatusConfigEntry) -> bool:
    """Unload a status page."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
