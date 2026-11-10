"""Config flow: pick a source, fill in its settings, then pick the services."""

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_COMPONENTS,
    CONF_PARAMS,
    CONF_PROVIDER,
    CONF_SOURCE,
    DOMAIN,
    PRESELECT_ALL_BELOW,
)
from .models import Snapshot
from .providers import PRESETS, PROVIDERS, Provider, ProviderError, build_provider


def _component_options(snapshot: Snapshot) -> list[SelectOptionDict]:
    """Groups first, then services, both alphabetically; label shows the group."""
    comps = sorted(
        snapshot.components.values(), key=lambda c: (not c.is_group, (c.group or c.name).lower(), c.name.lower())
    )
    options: list[SelectOptionDict] = []
    for comp in comps:
        label = comp.name
        if comp.is_group:
            label = f"▣ {comp.name}"
        elif comp.group and comp.group not in comp.name:
            label = f"{comp.name}  ({comp.group})"
        options.append(SelectOptionDict(value=comp.id, label=label))
    return options


def _default_selection(snapshot: Snapshot) -> list[str]:
    comps = list(snapshot.components.values())
    if len(comps) < PRESELECT_ALL_BELOW:
        return [c.id for c in comps]
    groups = [c.id for c in comps if c.is_group]
    return groups or [c.id for c in comps[:PRESELECT_ALL_BELOW]]


def _components_schema(snapshot: Snapshot, default: list[str]) -> vol.Schema:
    known = set(snapshot.components)
    return vol.Schema(
        {
            vol.Required(CONF_COMPONENTS, default=[d for d in default if d in known]): SelectSelector(
                SelectSelectorConfig(
                    options=_component_options(snapshot),
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                )
            )
        }
    )


async def _async_fetch(hass: HomeAssistant, provider: Provider) -> Snapshot:
    return await provider.async_fetch(async_get_clientsession(hass))


class HealthStatusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add one status page."""

    VERSION = 1

    def __init__(self) -> None:
        self._provider_type: str | None = None
        self._params: dict[str, Any] = {}
        self._provider: Provider | None = None
        self._snapshot: Snapshot | None = None
        self._previous: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose the source."""
        if user_input is not None:
            preset = PRESETS[user_input[CONF_SOURCE]]
            self._provider_type = preset["provider"]
            self._params = dict(preset["params"])
            return await self.async_step_settings()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SOURCE, default="ehealth"): SelectSelector(
                        SelectSelectorConfig(
                            options=list(PRESETS),
                            translation_key="source",
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    def _missing_fields(self) -> list[tuple[str, str, Any]]:
        assert self._provider_type
        return [f for f in PROVIDERS[self._provider_type].fields if f[0] not in self._params]

    def _settings_schema(self) -> vol.Schema:
        lang_default = "fr" if (self.hass.config.language or "").startswith("fr") else "nl"
        schema: dict[Any, Any] = {}
        for key, kind, default in self._missing_fields():
            previous = self._previous.get(key)
            if kind == "url":
                schema[vol.Required(key, description={"suggested_value": previous or default})] = TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                )
            elif kind == "language":
                schema[vol.Required(key, default=previous or lang_default)] = SelectSelector(
                    SelectSelectorConfig(options=["nl", "fr"], translation_key="language")
                )
            elif kind.startswith("select:"):
                schema[vol.Required(key, default=previous or default)] = SelectSelector(
                    SelectSelectorConfig(options=kind[7:].split(","), translation_key=key)
                )
        return vol.Schema(schema)

    async def async_step_settings(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask what the chosen source still needs (language, URL, sector), then test it."""
        errors: dict[str, str] = {}
        if user_input is not None or not self._missing_fields():
            self._params.update(user_input or {})
            if "url" in self._params:
                url = str(self._params["url"]).strip().rstrip("/")
                if not url.startswith(("http://", "https://")):
                    url = f"https://{url}"
                self._params["url"] = url
            self._provider = build_provider(self._provider_type, self._params)
            await self.async_set_unique_id(self._provider.unique_id)
            self._abort_if_unique_id_configured()
            try:
                self._snapshot = await _async_fetch(self.hass, self._provider)
            except ProviderError:
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_components()
            # Let the user correct the URL / settings.
            for key, _kind, _default in PROVIDERS[self._provider_type].fields:
                if key not in PRESETS_FIXED_KEYS and key in self._params:
                    self._previous[key] = self._params.pop(key)

        return self.async_show_form(
            step_id="settings", data_schema=self._settings_schema(), errors=errors
        )

    async def async_step_components(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick the services to create sensors for."""
        assert self._snapshot and self._provider
        if user_input is not None:
            title = self._params.get("name") or self._snapshot.title or self._provider.title
            return self.async_create_entry(
                title=title,
                data={CONF_PROVIDER: self._provider_type, CONF_PARAMS: self._params},
                options={CONF_COMPONENTS: user_input[CONF_COMPONENTS]},
            )
        return self.async_show_form(
            step_id="components",
            data_schema=_components_schema(self._snapshot, _default_selection(self._snapshot)),
            description_placeholders={"count": str(len(self._snapshot.components))},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> HealthStatusOptionsFlow:
        return HealthStatusOptionsFlow()


# Settings that a preset fills in and the user should not be asked again.
PRESETS_FIXED_KEYS = frozenset({"name"})


class HealthStatusOptionsFlow(OptionsFlowWithReload):
    """Change which services are monitored."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data={CONF_COMPONENTS: user_input[CONF_COMPONENTS]})

        coordinator = getattr(self.config_entry, "runtime_data", None)
        snapshot: Snapshot | None = getattr(coordinator, "data", None)
        if snapshot is None:
            provider = build_provider(
                self.config_entry.data[CONF_PROVIDER], dict(self.config_entry.data.get(CONF_PARAMS, {}))
            )
            try:
                snapshot = await _async_fetch(self.hass, provider)
            except ProviderError:
                return self.async_abort(reason="cannot_connect")

        current = list(self.config_entry.options.get(CONF_COMPONENTS, []))
        return self.async_show_form(
            step_id="init",
            data_schema=_components_schema(snapshot, current),
            description_placeholders={"count": str(len(snapshot.components))},
        )
