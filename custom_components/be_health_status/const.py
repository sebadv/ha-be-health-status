"""Constants for BE Health Status."""

from __future__ import annotations

DOMAIN = "be_health_status"

# Stored in the config entry options:
#   topics:     ["ehealth", "mycarenet", ...]   what the user ticked
#   sectors:    ["pharma", ...]                 MyCareNet sectors
#   sources:    {key: {provider, params, title}} one device each
#   components: {key: {component_id: name}}     the services to create sensors for
CONF_TOPICS = "topics"
CONF_SECTORS = "sectors"
CONF_SOURCES = "sources"
CONF_COMPONENTS = "components"
