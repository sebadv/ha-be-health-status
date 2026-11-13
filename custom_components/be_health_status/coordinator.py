"""Polling coordinators: one per source (= one status page, one device)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, ISSUE_PREFIX, ISSUES_URL
from .models import Snapshot
from .providers import Provider, ProviderError, build_provider

_LOGGER = logging.getLogger(__name__)

#: Raise a repair issue when a source keeps failing this long.
FAILING_FOR = timedelta(hours=2)


@dataclass
class SourceRuntime:
    """Everything the entities of one source need."""

    key: str
    title: str
    coordinator: SourceCoordinator
    #: component id -> name as stored at setup (kept when the page is down)
    components: dict[str, str] = field(default_factory=dict)


type HealthStatusConfigEntry = ConfigEntry[dict[str, SourceRuntime]]


def issue_id(key: str) -> str:
    """Repair issue id for a source."""
    return f"{ISSUE_PREFIX}{key}"


class SourceCoordinator(DataUpdateCoordinator[Snapshot]):
    """Fetches one status page on an interval."""

    config_entry: HealthStatusConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: HealthStatusConfigEntry, key: str, source: dict[str, Any]
    ) -> None:
        self.key = key
        self.title: str = source.get("title", key)
        self.provider: Provider = build_provider(source["provider"], dict(source.get("params", {})))
        self.failing_since: datetime | None = None
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {key}",
            update_interval=self.provider.scan_interval,
        )

    async def _async_update_data(self) -> Snapshot:
        try:
            snapshot = await self.provider.async_fetch(async_get_clientsession(self.hass))
        except ProviderError as err:
            self._note_failure(err)
            raise UpdateFailed(str(err)) from err
        if self.failing_since is not None:
            self.failing_since = None
            ir.async_delete_issue(self.hass, DOMAIN, issue_id(self.key))
        return snapshot

    def _note_failure(self, err: ProviderError) -> None:
        now = dt_util.utcnow()
        if self.failing_since is None:
            self.failing_since = now
        if now - self.failing_since < FAILING_FOR:
            return
        # The site is down for a long time, or (for pages read as HTML) was redesigned.
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id(self.key),
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            learn_more_url=ISSUES_URL,
            translation_key="source_failing",
            translation_placeholders={
                "source": self.title,
                "since": dt_util.as_local(self.failing_since).strftime("%d/%m/%Y %H:%M"),
                "error": str(err)[:300],
            },
        )
