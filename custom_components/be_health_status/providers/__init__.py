"""Registry of providers and of the topics a user can follow."""

from __future__ import annotations

from typing import Any

from ..models import Snapshot
from .arvato import ArvatoProvider
from .base import Provider, ProviderError
from .ehealth import EHealthProvider
from .ibz import IbzProvider
from .intermut import SECTORS, IntermutProvider
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

#: Topics offered in the setup, in display order.
TOPICS: tuple[str, ...] = ("ehealth", "careconnect", "itsme", "nmvs", "rijksregister", "mycarenet")

_SECTOR_LABELS = {
    "nl": {"pharma": "apothekers", "doctors": "artsen", "dentists": "tandartsen", "nurses": "verpleegkundigen"},
    "fr": {"pharma": "pharmaciens", "doctors": "médecins", "dentists": "dentistes", "nurses": "infirmiers"},
}


def build_sources(topics: list[str], sectors: list[str], lang: str) -> dict[str, dict[str, Any]]:
    """Turn the chosen topics into sources: key -> {provider, params, title}.

    Every source becomes one device. MyCareNet becomes one source per sector.
    """
    lang = "fr" if lang == "fr" else "nl"
    sources: dict[str, dict[str, Any]] = {}
    for topic in TOPICS:
        if topic not in topics:
            continue
        if topic == "ehealth":
            sources["ehealth"] = {"provider": "ehealth", "params": {"language": lang}, "title": "eHealth"}
        elif topic == "careconnect":
            sources["careconnect"] = {
                "provider": "pagerduty",
                "params": {"url": "https://status.careconnect.be"},
                "title": "CareConnect",
            }
        elif topic == "itsme":
            sources["itsme"] = {
                "provider": "statuspage",
                "params": {"url": "https://itsme.statuspage.io"},
                "title": "itsme",
            }
        elif topic == "nmvs":
            sources["nmvs"] = {"provider": "arvato_nmvs", "params": {}, "title": "NMVS"}
        elif topic == "rijksregister":
            sources["rijksregister"] = {
                "provider": "ibz",
                "params": {"language": lang},
                "title": "Rijksregister" if lang == "nl" else "Registre national",
            }
        elif topic == "mycarenet":
            for sector in SECTORS:
                if sector in sectors:
                    sources[f"mycarenet_{sector}"] = {
                        "provider": "intermut",
                        "params": {"sector": sector, "language": lang},
                        "title": f"MyCareNet {_SECTOR_LABELS[lang][sector]}",
                    }
    return sources


def default_selection(source_key: str, snapshot: Snapshot) -> list[str]:
    """Sensible pre-selection the first time a source is set up."""
    comps = list(snapshot.components.values())
    if source_key == "nmvs":
        return [c.id for c in comps if c.id.startswith("belgium")]
    if source_key == "ehealth":
        return [c.id for c in comps if c.is_group]
    return [c.id for c in comps]


def build_provider(provider_type: str, params: dict[str, Any]) -> Provider:
    """Instantiate a provider from stored settings."""
    try:
        cls = PROVIDERS[provider_type]
    except KeyError as err:
        raise ProviderError(f"unknown provider {provider_type!r}") from err
    return cls(params)


__all__ = [
    "PROVIDERS",
    "SECTORS",
    "TOPICS",
    "Provider",
    "ProviderError",
    "build_provider",
    "build_sources",
    "default_selection",
]
