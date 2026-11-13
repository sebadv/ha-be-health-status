"""Constants for BE Health Status."""

from __future__ import annotations

DOMAIN = "be_health_status"

# Stored in the config entry options:
#   language:   "nl" | "fr"                     language of the service names
#   topics:     ["ehealth", "mycarenet", ...]   what the user ticked
#   sectors:    ["pharma", ...]                 MyCareNet sectors
#   sources:    {key: {provider, params, title}} one device each
#   components: {key: {component_id: name}}     the services to create sensors for
#   scan_intervals: {topic | "calendar": minutes}  polling, set under Configure
CONF_TOPICS = "topics"
CONF_LANGUAGE = "language"
LANGUAGES = ("nl", "fr")
CONF_SECTORS = "sectors"
CONF_SOURCES = "sources"
CONF_COMPONENTS = "components"
CONF_SCAN_INTERVALS = "scan_intervals"

#: Interval key for the eHealth maintenance calendar and incident feed.
CALENDAR = "calendar"
#: Recommended polling, in minutes. JSON APIs are cheap; HTML pages are read less often.
DEFAULT_SCAN_MINUTES: dict[str, int] = {
    "ehealth": 2,
    "careconnect": 2,
    "itsme": 2,
    "nmvs": 2,
    "rijksregister": 5,
    "mycarenet": 5,
    CALENDAR: 10,
}
MIN_SCAN_MINUTES = 1
MAX_SCAN_MINUTES = 1440

ISSUE_PREFIX = "source_failing_"
ISSUES_URL = "https://github.com/sebadv/ha-be-health-status/issues"
