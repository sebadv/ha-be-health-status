"""A problem sensor per source, handy for notifications."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HealthStatusConfigEntry, SourceRuntime
from .entity import HealthStatusEntity, remove_stale_entities
from .models import PROBLEM_STATUSES

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HealthStatusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one problem sensor per source."""
    entities = [ProblemSensor(source) for source in entry.runtime_data.values()]
    async_add_entities(entities)
    remove_stale_entities(hass, entry, "binary_sensor", {e.unique_id for e in entities if e.unique_id})


class ProblemSensor(HealthStatusEntity, BinarySensorEntity):
    """On when a selected service is not operational or an incident is open."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "problem"

    def __init__(self, source: SourceRuntime) -> None:
        super().__init__(source, "problem")

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None

    @property
    def is_on(self) -> bool:
        return (
            any(c.status in PROBLEM_STATUSES for c in self.scope())
            or bool(self.relevant_events("incident"))
            or bool(self.ongoing_maintenance())
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "affected": [
                f"{c.name}: {c.raw_status or c.status.value}"
                for c in self.scope()
                if c.status in PROBLEM_STATUSES
            ],
            "incidents": [
                {k: v for k, v in {"title": e.name, "status": e.status, "impact": e.impact, "url": e.url, **e.details}.items() if v}
                for e in self.relevant_events("incident")
            ],
            "maintenance": [e.name for e in self.ongoing_maintenance()],
        }
