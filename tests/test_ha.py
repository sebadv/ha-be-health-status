"""Tests that run inside Home Assistant (CI only: needs pytest-homeassistant-custom-component)."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries  # noqa: E402
from homeassistant.config_entries import ConfigEntryState  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from homeassistant.helpers import device_registry as dr  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.be_health_status.const import DOMAIN  # noqa: E402
from custom_components.be_health_status.diagnostics import (  # noqa: E402
    async_get_config_entry_diagnostics,
)
from custom_components.be_health_status.providers import PROVIDERS, ProviderError  # noqa: E402
from custom_components.be_health_status.providers.arvato import parse_arvato  # noqa: E402
from custom_components.be_health_status.providers.ehealth import parse_ehealth  # noqa: E402
from custom_components.be_health_status.providers.ibz import parse_ibz  # noqa: E402
from custom_components.be_health_status.providers.intermut import parse_intermut  # noqa: E402
from custom_components.be_health_status.providers.pagerduty import parse_pagerduty  # noqa: E402
from custom_components.be_health_status.providers.statuspage import parse_statuspage  # noqa: E402

IAM = "group:AXAQooF-9v9nOdhekPYm"
RECIP = "944b9851f3bd2e4c4ca869a9d1e6d345"


@pytest.fixture
def snapshots(load_json, load_text) -> dict[str, Any]:
    """What every provider type answers; set a value to an exception to make it fail."""
    return {
        "ehealth": parse_ehealth(load_json("ehealth_components.json"), "nl"),
        "statuspage": parse_statuspage(load_json("statuspage_summary.json")),
        "pagerduty": parse_pagerduty(
            load_json("pagerduty_services.json"),
            load_json("pagerduty_impacted.json"),
            load_json("pagerduty_post_enums.json"),
        ),
        "arvato_nmvs": parse_arvato(load_json("arvato_services.json")),
        "ibz": parse_ibz(load_text("ibz_rijksregister.html"), "nl"),
        "intermut": parse_intermut(load_text("intermut_pharma.html"), "nl"),
    }


@pytest.fixture(autouse=True)
def mock_fetch(snapshots):
    """Replace every provider's network call by the fixtures above."""

    def make(provider_type: str):
        async def fetch(self, session):
            answer = snapshots[provider_type]
            if isinstance(answer, Exception):
                raise answer
            return answer

        return fetch

    patches = [patch.object(cls, "async_fetch", make(ptype)) for ptype, cls in PROVIDERS.items()]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


async def _setup_via_flow(hass: HomeAssistant) -> config_entries.ConfigEntry:
    """Add eHealth (IAM + Recip-e) and itsme (defaults) through the config flow."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"topics": ["itsme", "ehealth"]})
    assert result["step_id"] == "components"
    assert result["description_placeholders"]["source"] == "eHealth"  # topics keep their fixed order
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"components": [IAM, RECIP]})

    assert result["step_id"] == "components"
    assert result["description_placeholders"]["source"] == "itsme"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})  # keep the pre-selection
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return result["result"]


async def test_full_flow_creates_entry_and_entities(hass: HomeAssistant) -> None:
    entry = await _setup_via_flow(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.title == "BE Health Status"
    assert entry.options["topics"] == ["ehealth", "itsme"]
    assert set(entry.options["components"]["ehealth"]) == {IAM, RECIP}
    assert len(entry.options["components"]["itsme"]) == 8

    registry = er.async_get(hass)
    recip = registry.async_get_entity_id("sensor", DOMAIN, f"ehealth_c_{RECIP}")
    iam = registry.async_get_entity_id("sensor", DOMAIN, f"ehealth_c_{IAM}")
    assert hass.states.get(recip).state == "operational"
    assert hass.states.get(recip).attributes["raw_status"] == "Operationeel"
    assert hass.states.get(iam).state == "partial_outage"

    overall = registry.async_get_entity_id("sensor", DOMAIN, "ehealth_overall")
    assert hass.states.get(overall).state == "partial_outage"
    problem = registry.async_get_entity_id("binary_sensor", DOMAIN, "ehealth_problem")
    assert hass.states.get(problem).state == "on"

    maint = registry.async_get_entity_id("sensor", DOMAIN, "itsme_next_maintenance")
    assert hass.states.get(maint).state.startswith("2026-11-16T21:00:00")

    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert {d.name for d in devices} == {"eHealth", "itsme"}


async def test_only_one_entry(hass: HomeAssistant) -> None:
    await _setup_via_flow(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_no_topics_and_sectors_errors(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"topics": []})
    assert result["errors"] == {"base": "no_topics"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"topics": ["mycarenet"]})
    assert result["step_id"] == "sectors"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"sectors": []})
    assert result["errors"] == {"base": "no_sectors"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"sectors": ["pharma", "nurses"]})
    assert result["step_id"] == "components"
    assert result["description_placeholders"]["source"] == "MyCareNet apothekers"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["description_placeholders"]["source"] == "MyCareNet verpleegkundigen"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert set(result["result"].options["sources"]) == {"mycarenet_pharma", "mycarenet_nurses"}


async def test_unreachable_source_retry_and_skip(hass: HomeAssistant, snapshots) -> None:
    good = snapshots["ibz"]
    snapshots["ibz"] = ProviderError("down")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"topics": ["rijksregister", "nmvs"]})
    assert result["step_id"] == "components"  # NMVS comes first and answers
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "unreachable"
    assert result["description_placeholders"]["source"] == "Rijksregister"

    # Retry while still down: same step again
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"skip": False})
    assert result["step_id"] == "unreachable"
    # Back up: retry shows the services
    snapshots["ibz"] = good
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"skip": False})
    assert result["step_id"] == "components"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert sorted(result["result"].options["components"]["nmvs"]) == ["belgium-api-cer", "belgium-sg", "belgium-ws"]


async def test_options_flow_removes_untracked_topic(hass: HomeAssistant) -> None:
    entry = await _setup_via_flow(hass)
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, "itsme_overall")

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"topics": ["ehealth"]})
    assert result["step_id"] == "components"
    # previous choice is pre-filled; keep only Recip-e
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"components": [RECIP]})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert registry.async_get_entity_id("sensor", DOMAIN, "itsme_overall") is None
    assert registry.async_get_entity_id("sensor", DOMAIN, f"ehealth_c_{IAM}") is None
    assert registry.async_get_entity_id("sensor", DOMAIN, f"ehealth_c_{RECIP}")
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert {d.name for d in devices} == {"eHealth"}


async def test_one_failing_source_does_not_block_others(hass: HomeAssistant, snapshots) -> None:
    entry = await _setup_via_flow(hass)
    snapshots["statuspage"] = ProviderError("down")
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    registry = er.async_get(hass)
    assert hass.states.get(registry.async_get_entity_id("sensor", DOMAIN, "itsme_overall")).state == "unavailable"
    assert hass.states.get(registry.async_get_entity_id("sensor", DOMAIN, f"ehealth_c_{RECIP}")).state == "operational"


async def test_all_sources_failing_retries_setup(hass: HomeAssistant, snapshots) -> None:
    entry = await _setup_via_flow(hass)
    snapshots["statuspage"] = ProviderError("down")
    snapshots["ehealth"] = ProviderError("down")
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_migrate_from_0_1(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        title="eHealth",
        unique_id="ehealth_nl",
        data={"provider": "ehealth", "params": {"language": "nl"}},
        options={"components": [RECIP]},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.version == 2
    assert entry.state is ConfigEntryState.LOADED
    assert entry.options["sources"]["ehealth"]["provider"] == "ehealth"
    sensor = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"ehealth_c_{RECIP}")
    assert hass.states.get(sensor).name == "eHealth Recip-e Patient"


async def test_diagnostics(hass: HomeAssistant) -> None:
    entry = await _setup_via_flow(hass)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["sources"]["ehealth"]["last_update_success"] is True
    assert RECIP in diag["sources"]["ehealth"]["snapshot"]["components"]
