"""Status sensors: one per selected service, one overall, and next maintenance."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HealthStatusConfigEntry, HealthStatusCoordinator
from .entity import HealthStatusEntity
from .models import Status, worst
from .providers.statuspage import StatuspageProvider

PARALLEL_UPDATES = 0

STATUS_OPTIONS = [s.value for s in Status]
COMPONENT_PREFIX = "c_"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HealthStatusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create sensors for the selected services."""
    coordinator = entry.runtime_data
    selected: list[str] = list(entry.options.get("components", []))
    entities: list[SensorEntity] = [OverallStatusSensor(coordinator)]
    entities += [ComponentStatusSensor(coordinator, cid) for cid in selected]
    if isinstance(coordinator.provider, StatuspageProvider):
        entities.append(NextMaintenanceSensor(coordinator))
    async_add_entities(entities)

    # Drop the sensors of services that were deselected in the options.
    registry = er.async_get(hass)
    keep = {f"{entry.unique_id or entry.entry_id}_{COMPONENT_PREFIX}{cid}" for cid in selected}
    prefix = f"{entry.unique_id or entry.entry_id}_{COMPONENT_PREFIX}"
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (
            reg_entry.domain == "sensor"
            and reg_entry.unique_id.startswith(prefix)
            and reg_entry.unique_id not in keep
        ):
            registry.async_remove(reg_entry.entity_id)


class ComponentStatusSensor(HealthStatusEntity, SensorEntity):
    """Status of one service or group."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUS_OPTIONS
    _attr_translation_key = "status"

    def __init__(self, coordinator: HealthStatusCoordinator, component_id: str) -> None:
        super().__init__(coordinator, f"{COMPONENT_PREFIX}{component_id}")
        self._component_id = component_id
        comp = coordinator.data.components.get(component_id) if coordinator.data else None
        self._attr_name = comp.name if comp else component_id

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data is not None
            and self._component_id in self.coordinator.data.components
        )

    @property
    def native_value(self) -> str | None:
        comp = self.coordinator.data.components.get(self._component_id)
        return comp.status.value if comp else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        comp = self.coordinator.data.components.get(self._component_id)
        if comp is None:
            return {}
        attrs: dict[str, Any] = {
            "raw_status": comp.raw_status,
            "service_id": comp.id,
            "group": comp.group,
            "is_group": comp.is_group,
            "last_updated": comp.last_updated,
        }
        attrs.update({k: v for k, v in comp.extra.items() if v is not None})
        return {k: v for k, v in attrs.items() if v is not None}

    @callback
    def _handle_coordinator_update(self) -> None:
        comp = self.coordinator.data.components.get(self._component_id)
        if comp and comp.name != self._attr_name:
            self._attr_name = comp.name
        super()._handle_coordinator_update()


class OverallStatusSensor(HealthStatusEntity, SensorEntity):
    """Worst status among the selected services (all services when none are selected)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUS_OPTIONS
    _attr_translation_key = "overall"

    def __init__(self, coordinator: HealthStatusCoordinator) -> None:
        super().__init__(coordinator, "overall")

    def _scope(self):
        comps = self.selected_components()
        if not comps and self.coordinator.data:
            comps = list(self.coordinator.data.components.values())
        return comps

    @property
    def native_value(self) -> str:
        return worst([c.status for c in self._scope()]).value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        affected = [c for c in self._scope() if c.status != Status.OPERATIONAL]
        return {
            "affected": [f"{c.name}: {c.raw_status or c.status.value}" for c in affected],
            "monitored": len(self._scope()),
        }


class NextMaintenanceSensor(HealthStatusEntity, SensorEntity):
    """Start of the next announced maintenance (Statuspage pages)."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "next_maintenance"

    def __init__(self, coordinator: HealthStatusCoordinator) -> None:
        super().__init__(coordinator, "next_maintenance")

    @property
    def native_value(self) -> datetime | None:
        events = [e for e in self.relevant_events("maintenance") if e.starts_at]
        return events[0].starts_at if events else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        events = [e for e in self.relevant_events("maintenance") if e.starts_at]
        if not events:
            return {}
        nxt = events[0]
        return {
            "title": nxt.name,
            "ends_at": nxt.ends_at.isoformat() if nxt.ends_at else None,
            "url": nxt.url,
            "upcoming": [
                {"title": e.name, "starts_at": e.starts_at.isoformat(), "url": e.url}
                for e in events[:5]
            ],
        }
