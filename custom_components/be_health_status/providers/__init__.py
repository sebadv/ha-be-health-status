"""Registry of all status page providers."""

from __future__ import annotations

from typing import Any

from .arvato import ArvatoProvider
from .base import Provider, ProviderError
from .ehealth import EHealthProvider
from .ibz import IbzProvider
from .intermut import IntermutProvider
from .pagerduty import PagerDutyProvider
from .statuspage import StatuspageProvider

PROVIDERS: dict[str, type[Provider]] = {
    cls.type: cls
    for cls in (
        EHealthProvider,
        PagerDutyProvider,
        StatuspageProvider,
        ArvatoProvider,
        IbzProvider,
        IntermutProvider,
    )
}

# Ready-made choices offered in the config flow. "params" pre-fills the
# provider's fields; generic providers (Statuspage, PagerDuty) can also be
# added with any URL.
PRESETS: dict[str, dict[str, Any]] = {
    "ehealth": {"provider": "ehealth", "params": {}},
    "careconnect": {
        "provider": "pagerduty",
        "params": {"url": "https://status.careconnect.be", "name": "CareConnect"},
    },
    "itsme": {
        "provider": "statuspage",
        "params": {"url": "https://itsme.statuspage.io", "name": "itsme"},
    },
    "nmvs": {"provider": "arvato_nmvs", "params": {}},
    "rijksregister": {"provider": "ibz", "params": {}},
    "mycarenet": {"provider": "intermut", "params": {}},
    "statuspage": {"provider": "statuspage", "params": {}},
    "pagerduty": {"provider": "pagerduty", "params": {}},
}


def build_provider(provider_type: str, params: dict[str, Any]) -> Provider:
    """Instantiate a provider from what is stored in a config entry."""
    try:
        cls = PROVIDERS[provider_type]
    except KeyError as err:
        raise ProviderError(f"unknown provider {provider_type!r}") from err
    return cls(params)


__all__ = ["PRESETS", "PROVIDERS", "Provider", "ProviderError", "build_provider"]
