"""Polling coordinators: one per source (= one status page, one device)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .models import Snapshot
from .providers import Provider, ProviderError, build_provider

_LOGGER = logging.getLogger(__name__)


@dataclass
class SourceRuntime:
    """Everything the entities of one source need."""

    key: str
    title: str
    coordinator: SourceCoordinator
    #: component id -> name as stored at setup (kept when the page is down)
    components: dict[str, str] = field(default_factory=dict)


type HealthStatusConfigEntry = ConfigEntry[dict[str, SourceRuntime]]


class SourceCoordinator(DataUpdateCoordinator[Snapshot]):
    """Fetches one status page on an interval."""

    config_entry: HealthStatusConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: HealthStatusConfigEntry, key: str, source: dict[str, Any]
    ) -> None:
        self.key = key
        self.provider: Provider = build_provider(source["provider"], dict(source.get("params", {})))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {key}",
            update_interval=self.provider.scan_interval,
        )

    async def _async_update_data(self) -> Snapshot:
        try:
            return await self.provider.async_fetch(async_get_clientsession(self.hass))
        except ProviderError as err:
            raise UpdateFailed(str(err)) from err
