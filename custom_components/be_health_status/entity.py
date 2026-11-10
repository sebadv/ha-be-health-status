"""Shared entity base."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_COMPONENTS, DOMAIN
from .coordinator import HealthStatusCoordinator
from .models import Component, Event


class HealthStatusEntity(CoordinatorEntity[HealthStatusCoordinator]):
    """An entity belonging to one status page (one device per page)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HealthStatusCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=coordinator.provider.url,
        )

    @property
    def selected_ids(self) -> list[str]:
        return list(self.coordinator.config_entry.options.get(CONF_COMPONENTS, []))

    def selected_components(self) -> list[Component]:
        """Selected components that the page currently lists."""
        data = self.coordinator.data.components if self.coordinator.data else {}
        return [data[cid] for cid in self.selected_ids if cid in data]

    def relevant_events(self, kind: str) -> list[Event]:
        """Events touching a selected component, or the whole page when they name none."""
        if not self.coordinator.data:
            return []
        selected = set(self.selected_ids)
        events = (
            self.coordinator.data.incidents()
            if kind == "incident"
            else self.coordinator.data.maintenances()
        )
        return [e for e in events if not e.component_ids or selected & set(e.component_ids)]
