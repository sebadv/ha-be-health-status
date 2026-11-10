"""A problem sensor per status page, handy for notifications."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HealthStatusConfigEntry, HealthStatusCoordinator
from .entity import HealthStatusEntity
from .models import PROBLEM_STATUSES

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HealthStatusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the problem sensor."""
    async_add_entities([ProblemSensor(entry.runtime_data)])


class ProblemSensor(HealthStatusEntity, BinarySensorEntity):
    """On when a selected service is not operational or an incident is open."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "problem"

    def __init__(self, coordinator: HealthStatusCoordinator) -> None:
        super().__init__(coordinator, "problem")

    def _scope(self):
        comps = self.selected_components()
        if not comps and self.coordinator.data:
            comps = list(self.coordinator.data.components.values())
        return comps

    @property
    def is_on(self) -> bool:
        return any(c.status in PROBLEM_STATUSES for c in self._scope()) or bool(
            self.relevant_events("incident")
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "affected": [
                f"{c.name}: {c.raw_status or c.status.value}"
                for c in self._scope()
                if c.status in PROBLEM_STATUSES
            ],
            "incidents": [
                {"title": e.name, "status": e.status, "impact": e.impact, "url": e.url}
                for e in self.relevant_events("incident")
            ],
        }
