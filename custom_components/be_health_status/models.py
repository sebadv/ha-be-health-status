"""Shared data model for all status providers.

Providers translate whatever a status page publishes into this model, so the
rest of the integration (entities, config flow) never deals with page specifics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class Status(StrEnum):
    """Normalised status of a service, ordered from good to bad by SEVERITY."""

    OPERATIONAL = "operational"
    MAINTENANCE = "maintenance"
    DEGRADED = "degraded"
    PARTIAL_OUTAGE = "partial_outage"
    MAJOR_OUTAGE = "major_outage"
    UNKNOWN = "unknown"


# Higher means worse. UNKNOWN sits below every real problem so that a single
# unknown member never hides an outage elsewhere in a group.
SEVERITY: dict[Status, int] = {
    Status.OPERATIONAL: 0,
    Status.UNKNOWN: 1,
    Status.MAINTENANCE: 2,
    Status.DEGRADED: 3,
    Status.PARTIAL_OUTAGE: 4,
    Status.MAJOR_OUTAGE: 5,
}

PROBLEM_STATUSES = frozenset(
    {Status.MAINTENANCE, Status.DEGRADED, Status.PARTIAL_OUTAGE, Status.MAJOR_OUTAGE}
)


def worst(statuses: list[Status] | tuple[Status, ...] | set[Status]) -> Status:
    """Return the most severe status, or UNKNOWN for an empty collection."""
    if not statuses:
        return Status.UNKNOWN
    return max(statuses, key=lambda s: SEVERITY[s])


@dataclass(slots=True)
class Component:
    """One monitored service (or group of services) on a status page."""

    id: str
    name: str
    status: Status
    raw_status: str | None = None
    group: str | None = None
    is_group: bool = False
    last_updated: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Event:
    """An incident or (planned) maintenance announced on a status page."""

    id: str
    name: str
    kind: str  # "incident" or "maintenance"
    status: str | None = None
    impact: str | None = None
    url: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    component_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Snapshot:
    """Everything a provider knows after one poll."""

    components: dict[str, Component]
    events: list[Event] = field(default_factory=list)
    #: Name the page gives itself, used as default entry title.
    title: str | None = None

    def incidents(self) -> list[Event]:
        """Active incidents."""
        return [e for e in self.events if e.kind == "incident"]

    def maintenances(self) -> list[Event]:
        """Announced maintenances, soonest first."""
        items = [e for e in self.events if e.kind == "maintenance"]
        dated = sorted((e for e in items if e.starts_at), key=lambda e: e.starts_at)
        return dated + [e for e in items if not e.starts_at]
