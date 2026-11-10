"""Shared entity base: every entity belongs to one source (one device)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SourceCoordinator, SourceRuntime
from .models import Component, Event


def entity_unique_id(source_key: str, key: str) -> str:
    """unique_id of an entity of a source."""
    return f"{source_key}_{key}"


def remove_stale_entities(hass, entry: ConfigEntry, domain: str, keep: set[str]) -> None:
    """Remove this entry's entities of a platform that are no longer created."""
    registry = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.domain == domain and reg_entry.unique_id not in keep:
            registry.async_remove(reg_entry.entity_id)


class HealthStatusEntity(CoordinatorEntity[SourceCoordinator]):
    """An entity of one source."""

    _attr_has_entity_name = True

    def __init__(self, source: SourceRuntime, key: str) -> None:
        super().__init__(source.coordinator)
        self.source = source
        entry = source.coordinator.config_entry
        self._attr_unique_id = entity_unique_id(source.key, key)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{source.key}")},
            name=source.title,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=source.coordinator.provider.url,
        )

    def selected_components(self) -> list[Component]:
        """Selected components that the page currently lists."""
        data = self.coordinator.data.components if self.coordinator.data else {}
        return [data[cid] for cid in self.source.components if cid in data]

    def scope(self) -> list[Component]:
        """Selected components, or everything on the page when nothing is selected."""
        comps = self.selected_components()
        if not comps and not self.source.components and self.coordinator.data:
            comps = list(self.coordinator.data.components.values())
        return comps

    def relevant_events(self, kind: str) -> list[Event]:
        """Events touching a selected component, or the whole page when they name none."""
        if not self.coordinator.data:
            return []
        selected = set(self.source.components)
        events = (
            self.coordinator.data.incidents()
            if kind == "incident"
            else self.coordinator.data.maintenances()
        )
        return [e for e in events if not e.component_ids or not selected or selected & set(e.component_ids)]
