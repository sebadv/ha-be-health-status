"""Constants for BE Health Status."""

from __future__ import annotations

DOMAIN = "be_health_status"

CONF_PROVIDER = "provider"
CONF_PARAMS = "params"
CONF_COMPONENTS = "components"
CONF_SOURCE = "source"

# Above this many components, the setup pre-selects only the groups.
PRESELECT_ALL_BELOW = 16
