"""Base class and HTTP helpers shared by every provider."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, ClassVar

import aiohttp

from ..models import Snapshot

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
USER_AGENT = "HomeAssistant-BE-Health-Status (+https://github.com/sebadv/ha-be-health-status)"


class ProviderError(Exception):
    """Raised when a status page cannot be fetched or understood."""


class Provider(ABC):
    """A source of service statuses (one status page)."""

    #: Stable identifier stored in the config entry.
    type: ClassVar[str]
    #: How often to poll. JSON APIs are cheap; HTML pages are polled less often.
    scan_interval: ClassVar[timedelta] = timedelta(minutes=2)
    #: Whether the source announces (planned) maintenance.
    has_maintenance: ClassVar[bool] = False

    def __init__(self, params: dict[str, Any]) -> None:
        self.params = params

    @property
    def url(self) -> str | None:
        """Public page a user can open, if any."""
        return None

    @abstractmethod
    async def async_fetch(self, session: aiohttp.ClientSession) -> Snapshot:
        """Fetch and parse the current state."""


async def get_json(session: aiohttp.ClientSession, url: str) -> Any:
    """GET a URL and decode JSON, raising ProviderError on any failure."""
    try:
        async with session.get(
            url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
        ) as resp:
            if resp.status != 200:
                raise ProviderError(f"{url} answered HTTP {resp.status}")
            return await resp.json(content_type=None)
    except asyncio.TimeoutError as err:
        raise ProviderError(f"{url} did not answer within {REQUEST_TIMEOUT.total:.0f}s") from err
    except (aiohttp.ClientError, ValueError) as err:
        raise ProviderError(f"{url}: {type(err).__name__}: {err}") from err


async def get_text(session: aiohttp.ClientSession, url: str) -> str:
    """GET a URL and return the body as text, raising ProviderError on any failure."""
    try:
        async with session.get(
            url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT}
        ) as resp:
            if resp.status != 200:
                raise ProviderError(f"{url} answered HTTP {resp.status}")
            return await resp.text()
    except asyncio.TimeoutError as err:
        raise ProviderError(f"{url} did not answer within {REQUEST_TIMEOUT.total:.0f}s") from err
    except aiohttp.ClientError as err:
        raise ProviderError(f"{url}: {type(err).__name__}: {err}") from err


def parse_datetime(value: Any) -> datetime | None:
    """Parse the ISO-like timestamps status pages use; None when unparsable."""
    if not value or not isinstance(value, str):
        return None
    text = value.strip().replace("Z", "+00:00")
    # "2026-11-10 12:30:00.278" (eHealth) has a space instead of a T.
    if len(text) > 10 and text[10] == " ":
        text = text[:10] + "T" + text[11:]
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None
