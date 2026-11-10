"""Status sensors: one per selected service, one overall per source, next maintenance."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HealthStatusConfigEntry, SourceRuntime
from .entity import HealthStatusEntity, remove_stale_entities
from .models import Status, worst
from .providers.statuspage import StatuspageProvider

PARALLEL_UPDATES = 0

STATUS_OPTIONS = [s.value for s in Status]


def _component_key(component_id: str) -> str:
    return f"c_{component_id}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HealthStatusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the sensors of every source."""
    entities: list[SensorEntity] = []
    for source in entry.runtime_data.values():
        entities.append(OverallStatusSensor(source))
        entities += [ComponentStatusSensor(source, cid, name) for cid, name in source.components.items()]
        if isinstance(source.coordinator.provider, StatuspageProvider):
            entities.append(NextMaintenanceSensor(source))
    async_add_entities(entities)
    remove_stale_entities(hass, entry, "sensor", {e.unique_id for e in entities if e.unique_id})


class ComponentStatusSensor(HealthStatusEntity, SensorEntity):
    """Status of one service or group."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUS_OPTIONS
    _attr_translation_key = "status"

    def __init__(self, source: SourceRuntime, component_id: str, name: str) -> None:
        super().__init__(source, _component_key(component_id))
        self._component_id = component_id
        comp = source.coordinator.data.components.get(component_id) if source.coordinator.data else None
        self._attr_name = comp.name if comp and name == component_id else name

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data is not None
            and self._component_id in self.coordinator.data.components
        )

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        comp = self.coordinator.data.components.get(self._component_id)
        return comp.status.value if comp else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        comp = self.coordinator.data.components.get(self._component_id) if self.coordinator.data else None
        if comp is None:
            return {}
        attrs: dict[str, Any] = {
            "raw_status": comp.raw_status,
            "service_id": comp.id,
            "group": comp.group,
            "is_group": comp.is_group,
            "last_updated": comp.last_updated,
        }
        attrs.update(comp.extra)
        return {k: v for k, v in attrs.items() if v is not None}


class OverallStatusSensor(HealthStatusEntity, SensorEntity):
    """Worst status among the selected services of a source."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUS_OPTIONS
    _attr_translation_key = "overall"

    def __init__(self, source: SourceRuntime) -> None:
        super().__init__(source, "overall")

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None

    @property
    def native_value(self) -> str:
        return worst([c.status for c in self.scope()]).value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        scope = self.scope()
        return {
            "affected": [
                f"{c.name}: {c.raw_status or c.status.value}" for c in scope if c.status != Status.OPERATIONAL
            ],
            "monitored": len(scope),
        }


class NextMaintenanceSensor(HealthStatusEntity, SensorEntity):
    """Start of the next announced maintenance (itsme)."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "next_maintenance"

    def __init__(self, source: SourceRuntime) -> None:
        super().__init__(source, "next_maintenance")

    def _events(self):
        return [e for e in self.relevant_events("maintenance") if e.starts_at]

    @property
    def native_value(self) -> datetime | None:
        events = self._events()
        return events[0].starts_at if events else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        events = self._events()
        if not events:
            return {}
        nxt = events[0]
        return {
            "title": nxt.name,
            "ends_at": nxt.ends_at.isoformat() if nxt.ends_at else None,
            "url": nxt.url,
            "upcoming": [
                {"title": e.name, "starts_at": e.starts_at.isoformat(), "url": e.url} for e in events[:5]
            ],
        }


