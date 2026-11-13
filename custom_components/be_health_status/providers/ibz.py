"""National Register services (IBZ / FOD Binnenlandse Zaken).

The IBZ site shows a small status block (Rijksregister, BELPIC, BAEC) with a
coloured dot and a tooltip on every page.
"""

from __future__ import annotations

from datetime import timedelta

import aiohttp

from ..models import Component, Snapshot, Status
from .base import Provider, ProviderError, get_text
from .htmltree import parse_html

PAGES = {
    "nl": "https://www.ibz.rrn.fgov.be/nl/professioneel/rijksregister",
    "fr": "https://www.ibz.rrn.fgov.be/fr/professionnel/registre-national",
}

_COLOURS = {
    "status-green": Status.OPERATIONAL,
    "status-orange": Status.DEGRADED,
    "status-red": Status.MAJOR_OUTAGE,
    "status-grey": Status.UNKNOWN,
    "status-gray": Status.UNKNOWN,
}

_NAMES = {
    "nl": {"RN": "Rijksregister", "BELPIC": "BELPIC (eID)", "BAEC": "BAEC (burgerlijke stand)"},
    "fr": {"RN": "Registre national", "BELPIC": "BELPIC (eID)", "BAEC": "BAEC (état civil)"},
}


def parse_ibz(html: str, lang: str = "nl") -> Snapshot:
    """Read the service-status block."""
    root = parse_html(html)
    block = root.find(cls="block-ibz-service-status") or root.find(cls="service-status-block")
    if block is None:
        raise ProviderError("IBZ page has no service status block")

    components: dict[str, Component] = {}
    for item in block.find_all("li", "service-status-item"):
        icon = item.find(cls="service-status-icon")
        label = item.find(cls="service-status-text")
        key = (label.text() if label else "").replace(" ", "").upper()
        if not key:
            continue
        status = next(
            (s for c, s in _COLOURS.items() if icon is not None and c in icon.classes),
            Status.UNKNOWN,
        )
        components[key.lower()] = Component(
            id=key.lower(),
            name=_NAMES.get(lang, _NAMES["nl"]).get(key, key),
            status=status,
            raw_status=item.attrs.get("data-tooltip") or None,
        )
    if not components:
        raise ProviderError("IBZ status block is empty")
    return Snapshot(components=components, title="Rijksregister" if lang == "nl" else "Registre national")


class IbzProvider(Provider):
    """Rijksregister / Registre national."""

    type = "ibz"
    scan_interval = timedelta(minutes=5)

    @property
    def lang(self) -> str:
        return "fr" if self.params.get("language") == "fr" else "nl"

    @property
    def url(self) -> str:
        return PAGES[self.lang]

    async def async_fetch(self, session: aiohttp.ClientSession) -> Snapshot:
        return parse_ibz(await get_text(session, PAGES[self.lang]), self.lang)
