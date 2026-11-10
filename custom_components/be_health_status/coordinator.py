"""Polling coordinator: one per config entry (= one status page)."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_PARAMS, CONF_PROVIDER, DOMAIN
from .models import Snapshot
from .providers import Provider, ProviderError, build_provider

_LOGGER = logging.getLogger(__name__)

type HealthStatusConfigEntry = ConfigEntry[HealthStatusCoordinator]


class HealthStatusCoordinator(DataUpdateCoordinator[Snapshot]):
    """Fetches one status page on an interval."""

    config_entry: HealthStatusConfigEntry

    def __init__(self, hass: HomeAssistant, entry: HealthStatusConfigEntry) -> None:
        self.provider: Provider = build_provider(
            entry.data[CONF_PROVIDER], dict(entry.data.get(CONF_PARAMS, {}))
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=self.provider.scan_interval,
        )

    async def _async_update_data(self) -> Snapshot:
        try:
            return await self.provider.async_fetch(async_get_clientsession(self.hass))
        except ProviderError as err:
            raise UpdateFailed(str(err)) from err
