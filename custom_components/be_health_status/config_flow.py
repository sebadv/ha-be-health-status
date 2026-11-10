"""Setup: tick the topics to follow, then pick the services of each topic.

The integration is added once. Both the initial setup and "Configure" walk
through the same steps:

1. ``user`` / ``init``: which topics (eHealth, CareConnect, itsme, ...)
2. ``sectors``: which MyCareNet sectors (only when MyCareNet is ticked)
3. ``components``: once per source, which of its services become sensors
"""

from __future__ import annotations

from typing import Any

try:  # Home Assistant 2026.11 replaced voluptuous by probatio (same API).
    import probatio as vol
except ImportError:  # pragma: no cover - older Home Assistant
    import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_COMPONENTS, CONF_SECTORS, CONF_SOURCES, CONF_TOPICS, DOMAIN
from .models import Snapshot
from .providers import (
    SECTORS,
    TOPICS,
    ProviderError,
    build_provider,
    build_sources,
    default_selection,
    ordered_for_display,
)

CONF_SKIP = "skip"


def _component_options(snapshot: Snapshot) -> list[SelectOptionDict]:
    """Each group followed by its services, in the order of the status page."""
    options: list[SelectOptionDict] = []
    for comp, is_member in ordered_for_display(snapshot):
        if comp.is_group:
            label = f"▣ {comp.name}"
        elif is_member:
            label = f"   ↳ {comp.name}"
        elif comp.group:
            label = f"{comp.name}  ({comp.group})"
        else:
            label = comp.name
        options.append(SelectOptionDict(value=comp.id, label=label))
    return options


class _SetupSteps:
    """Steps shared by the config flow and the options flow."""

    hass: Any
    _topics: list[str]
    _sectors: list[str]
    _sources: dict[str, dict[str, Any]]
    _components: dict[str, dict[str, str]]
    _previous_components: dict[str, dict[str, str]]
    _queue: list[str]
    _snapshot: Snapshot | None

    def _init_state(self, options: dict[str, Any] | None = None) -> None:
        options = options or {}
        self._topics = list(options.get(CONF_TOPICS, []))
        self._sectors = list(options.get(CONF_SECTORS, ["pharma"]))
        self._previous_components = {k: dict(v) for k, v in options.get(CONF_COMPONENTS, {}).items()}
        self._sources = {}
        self._components = {}
        self._queue = []
        self._snapshot = None

    @property
    def _lang(self) -> str:
        return "fr" if (self.hass.config.language or "").startswith("fr") else "nl"

    def _topics_schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_TOPICS, default=self._topics): SelectSelector(
                    SelectSelectorConfig(
                        options=list(TOPICS),
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                        translation_key="topic",
                    )
                )
            }
        )

    async def _after_topics(self, topics: list[str]) -> ConfigFlowResult:
        self._topics = [t for t in TOPICS if t in topics]
        if not self._topics:
            return self.async_show_form(  # type: ignore[attr-defined]
                step_id=self._first_step_id,  # type: ignore[attr-defined]
                data_schema=self._topics_schema(),
                errors={"base": "no_topics"},
            )
        if "mycarenet" in self._topics:
            return await self.async_step_sectors()
        return await self._start_sources()

    async def async_step_sectors(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Which MyCareNet sectors."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._sectors = [s for s in SECTORS if s in user_input[CONF_SECTORS]]
            if self._sectors:
                return await self._start_sources()
            errors["base"] = "no_sectors"
        return self.async_show_form(  # type: ignore[attr-defined]
            step_id="sectors",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SECTORS, default=self._sectors): SelectSelector(
                        SelectSelectorConfig(
                            options=list(SECTORS),
                            multiple=True,
                            mode=SelectSelectorMode.LIST,
                            translation_key="sector",
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def _start_sources(self) -> ConfigFlowResult:
        self._sources = build_sources(self._topics, self._sectors, self._lang)
        self._queue = list(self._sources)
        self._components = {}
        return await self._next_source()

    async def _next_source(self) -> ConfigFlowResult:
        if not self._queue:
            return self._finish()
        key = self._queue[0]
        source = self._sources[key]
        provider = build_provider(source["provider"], source["params"])
        try:
            self._snapshot = await provider.async_fetch(async_get_clientsession(self.hass))
        except ProviderError:
            self._snapshot = None
        return self._show_components()

    def _show_components(self, errors: dict[str, str] | None = None) -> ConfigFlowResult:
        key = self._queue[0]
        title = self._sources[key]["title"]
        snap = self._snapshot
        if snap is None:
            # Unreachable now: offer to retry or to keep the earlier choice.
            return self.async_show_form(  # type: ignore[attr-defined]
                step_id="unreachable",
                data_schema=vol.Schema({vol.Required(CONF_SKIP, default=False): BooleanSelector()}),
                description_placeholders={"source": title},
            )
        previous = self._previous_components.get(key)
        default = list(previous) if previous is not None else default_selection(key, snap)
        default = [d for d in default if d in snap.components]
        return self.async_show_form(  # type: ignore[attr-defined]
            step_id="components",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_COMPONENTS, default=default): SelectSelector(
                        SelectSelectorConfig(
                            options=_component_options(snap),
                            multiple=True,
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
            description_placeholders={"source": title, "count": str(len(snap.components))},
            errors=errors,
        )

    async def async_step_components(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Which services of the current source."""
        if user_input is None or self._snapshot is None:
            return self._show_components()
        key = self._queue.pop(0)
        chosen = [c for c in user_input.get(CONF_COMPONENTS, []) if c in self._snapshot.components]
        self._components[key] = {cid: self._snapshot.components[cid].name for cid in chosen}
        return await self._next_source()

    async def async_step_unreachable(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """A source did not answer: retry, or keep what was chosen before."""
        if user_input is not None and user_input.get(CONF_SKIP):
            key = self._queue.pop(0)
            self._components[key] = dict(self._previous_components.get(key, {}))
            return await self._next_source()
        return await self._next_source()

    def _options_data(self) -> dict[str, Any]:
        return {
            CONF_TOPICS: self._topics,
            CONF_SECTORS: self._sectors,
            CONF_SOURCES: self._sources,
            CONF_COMPONENTS: self._components,
        }

    def _finish(self) -> ConfigFlowResult:
        raise NotImplementedError


class HealthStatusConfigFlow(_SetupSteps, ConfigFlow, domain=DOMAIN):
    """Add the integration (once)."""

    VERSION = 2
    _first_step_id = "user"

    def __init__(self) -> None:
        self._init_state()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Which topics to follow."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return await self._after_topics(user_input[CONF_TOPICS])
        return self.async_show_form(step_id="user", data_schema=self._topics_schema())

    def _finish(self) -> ConfigFlowResult:
        return self.async_create_entry(title="BE Health Status", data={}, options=self._options_data())

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> HealthStatusOptionsFlow:
        return HealthStatusOptionsFlow()


class HealthStatusOptionsFlow(_SetupSteps, OptionsFlowWithReload):
    """Change topics and services ("Configure")."""

    _first_step_id = "init"

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Which topics to follow."""
        if user_input is not None:
            return await self._after_topics(user_input[CONF_TOPICS])
        self._init_state(dict(self.config_entry.options))
        return self.async_show_form(step_id="init", data_schema=self._topics_schema())

    def _finish(self) -> ConfigFlowResult:
        return self.async_create_entry(data=self._options_data())
