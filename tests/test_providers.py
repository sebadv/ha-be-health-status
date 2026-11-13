"""Parser tests against captured (and partly edited) status page data.

Fixtures are real answers captured on 2026-11-10; statuses were edited in some
of them so every normalised state is exercised.
"""

from __future__ import annotations

from datetime import UTC

import pytest

from custom_components.be_health_status.models import SEVERITY, Status, worst
from custom_components.be_health_status.providers import (
    PROVIDERS,
    TOPICS,
    build_provider,
    build_sources,
    default_selection,
)
from custom_components.be_health_status.providers.arvato import parse_arvato
from custom_components.be_health_status.providers.base import ProviderError, parse_datetime
from custom_components.be_health_status.providers.ehealth import (
    group_component_id,
    parse_ehealth,
    status_from_ehealth,
)
from custom_components.be_health_status.providers.ibz import parse_ibz
from custom_components.be_health_status.providers.intermut import parse_intermut
from custom_components.be_health_status.providers.pagerduty import parse_pagerduty
from custom_components.be_health_status.providers.statuspage import parse_statuspage


def test_worst_orders_by_severity():
    assert worst([Status.OPERATIONAL, Status.DEGRADED, Status.UNKNOWN]) == Status.DEGRADED
    assert worst([Status.OPERATIONAL, Status.UNKNOWN]) == Status.UNKNOWN
    assert worst([]) == Status.UNKNOWN
    assert set(SEVERITY) == set(Status)


# --- eHealth ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "name", "expected"),
    [
        (1, "Operationeel", Status.OPERATIONAL),
        (1, "Opérationnel", Status.OPERATIONAL),
        (2, "Verminderde prestaties", Status.DEGRADED),
        (2, "Performances dégradées", Status.DEGRADED),
        (3, "Gedeeltelijke onderbreking", Status.PARTIAL_OUTAGE),
        (3, "Interruption partielle", Status.PARTIAL_OUTAGE),
        (4, "Volledige onderbreking", Status.MAJOR_OUTAGE),
        (4, "Niet beschikbaar", Status.MAJOR_OUTAGE),
        (5, "Gepland onderhoud", Status.MAINTENANCE),
        (1, None, Status.OPERATIONAL),
        (9, "???", Status.UNKNOWN),
    ],
)
def test_ehealth_status_mapping(code, name, expected):
    assert status_from_ehealth(code, name) == expected


def test_ehealth_services_and_groups(load_json):
    snap = parse_ehealth(load_json("ehealth_components.json"), "nl")
    recip = snap.components["944b9851f3bd2e4c4ca869a9d1e6d345"]
    assert recip.name == "Recip-e Patient"
    assert recip.status == Status.OPERATIONAL
    assert recip.raw_status == "Operationeel"
    assert recip.group == "WebService"

    vitalink = snap.components["7fe4937f59a96b03086b323b36622a88"]
    assert vitalink.status == Status.MAINTENANCE

    iam = snap.components[group_component_id("AXAQooF-9v9nOdhekPYm")]
    assert iam.is_group
    assert iam.name == "IAM"
    assert iam.position == 1
    assert iam.extra["full_name"] == "1. IAM - Identity & Access Management"
    assert iam.status == Status.PARTIAL_OUTAGE  # worst member
    assert iam.raw_status == "Gedeeltelijke onderbreking"
    assert len(iam.extra["members"]) == 2

    webservice = snap.components[group_component_id("AXCqdw9UPi6_bix3D-gM")]
    assert webservice.status == Status.DEGRADED


def test_ehealth_french_names(load_json):
    snap = parse_ehealth(load_json("ehealth_components.json"), "fr")
    assert snap.components["ecc5eb1c47b50de3107a04663112e303"].name == "WebService Codage Seals"


def test_ehealth_bad_payload():
    with pytest.raises(ProviderError):
        parse_ehealth({"data": "nope"}, "nl")
    with pytest.raises(ProviderError):
        parse_ehealth({"data": []}, "nl")


# --- PagerDuty (CareConnect) -----------------------------------------------


def test_pagerduty_all_operational(load_json):
    snap = parse_pagerduty(
        load_json("pagerduty_services.json"),
        load_json("pagerduty_impacted_empty.json"),
        load_json("pagerduty_post_enums.json"),
    )
    assert "POLD000" not in snap.components  # inactive service skipped
    assert all(c.status == Status.OPERATIONAL for c in snap.components.values())
    assert snap.components["P4R10EJ"].name == "CareConnect General Issues"


def test_pagerduty_impacts(load_json):
    snap = parse_pagerduty(
        load_json("pagerduty_services.json"),
        load_json("pagerduty_impacted.json"),
        load_json("pagerduty_post_enums.json"),
    )
    assert snap.components["PJAM0PD"].status == Status.PARTIAL_OUTAGE
    assert snap.components["PJAM0PD"].raw_status == "partial outage"
    # Two impacts on Helena: the worst one wins.
    assert snap.components["PIMTHNB"].status == Status.MAJOR_OUTAGE
    assert snap.components["PIMTHNB"].raw_status == "outage"
    assert snap.components["PFQ5GYO"].status == Status.MAINTENANCE
    assert snap.components["P0ED02W"].status == Status.OPERATIONAL


def test_pagerduty_unknown_severity_is_still_a_problem(load_json):
    impacted = {"impacted_services": [{"service_id": "P0ED02W", "impact_severity_id": "NOPE"}]}
    snap = parse_pagerduty(load_json("pagerduty_services.json"), impacted, {"post_enums": []})
    assert snap.components["P0ED02W"].status == Status.DEGRADED


# --- Statuspage (itsme) ----------------------------------------------------


def test_statuspage_components(load_json):
    snap = parse_statuspage(load_json("statuspage_summary.json"))
    assert snap.title == "itsme"
    c = snap.components
    assert c["ytx6xs5fd1rt"].status == Status.OPERATIONAL
    assert c["05mdtlg1ks21"].status == Status.DEGRADED
    assert c["9l23mnqzn6rr"].status == Status.MAJOR_OUTAGE
    assert c["st9cvs26vbgy"].status == Status.MAINTENANCE
    assert c["f63l79t1f387"].status == Status.PARTIAL_OUTAGE
    assert c["9l23mnqzn6rr"].group == "Identity"
    assert c["kr8g5l4gb6vj"].is_group
    assert c["37tkz8wmz3z4"].group is None


def test_statuspage_events(load_json):
    snap = parse_statuspage(load_json("statuspage_summary.json"))
    assert [e.id for e in snap.incidents()] == ["rdckbjsqrjrc"]
    maint = snap.maintenances()
    assert [m.name for m in maint] == ["itsme® Maintenance 26R23", "itsme® Maintenance 26R24"]
    assert maint[0].starts_at.isoformat() == "2026-11-16T22:00:00+01:00"
    assert maint[0].ends_at.isoformat() == "2026-11-17T01:00:00+01:00"
    assert "st9cvs26vbgy" in maint[0].component_ids


def test_statuspage_resolved_incidents_are_ignored(load_json):
    data = load_json("statuspage_summary.json")
    data["incidents"][0]["status"] = "resolved"
    assert parse_statuspage(data).incidents() == []


# --- Arvato (NMVS) ---------------------------------------------------------


def test_arvato(load_json):
    snap = parse_arvato(load_json("arvato_services.json"))
    be = snap.components["belgium-sg"]
    assert be.name == "NMVS Belgium"
    assert be.is_group
    assert be.status == Status.OPERATIONAL
    assert snap.components["belgium-ws"].status == Status.OPERATIONAL
    assert snap.components["belgium-ws"].name == "NMVS Belgium ws-* endpoints"
    assert snap.components["belgium-api-cer"].status == Status.DEGRADED
    assert snap.components["belgium-api-cer"].raw_status == "Available, but degraded"
    assert snap.components["netherlands-ws"].status == Status.MAJOR_OUTAGE
    # outdated data is never reported as fine
    assert snap.components["netherlands-api-cer"].status == Status.UNKNOWN


# --- IBZ (Rijksregister) ---------------------------------------------------


def test_ibz(load_text):
    snap = parse_ibz(load_text("ibz_rijksregister.html"), "nl")
    assert snap.components["rn"].name == "Rijksregister"
    assert snap.components["rn"].status == Status.OPERATIONAL
    assert snap.components["rn"].raw_status == "Het Rijksregister is stabiel."
    assert snap.components["belpic"].status == Status.DEGRADED  # "BEL<br>PIC"
    assert snap.components["baec"].status == Status.MAJOR_OUTAGE
    assert snap.components["xyz"].status == Status.UNKNOWN


def test_ibz_missing_block():
    with pytest.raises(ProviderError):
        parse_ibz("<html><body>niets</body></html>")


# --- Intermut (MyCareNet) --------------------------------------------------


def test_intermut(load_text):
    snap = parse_intermut(load_text("intermut_pharma.html"), "nl")
    sec = "raadpleging_akkoord_hoofdstuk_iv_met_onmiddellijk_antwoord"
    avail = snap.components[f"{sec}__beschikbaarheid"]
    assert avail.status == Status.OPERATIONAL
    assert avail.raw_status == "Normaal"
    assert avail.name == "Raadpleging akkoord hoofdstuk IV met onmiddellijk antwoord – Beschikbaarheid"
    assert snap.components[f"{sec}__reactietijd"].status == Status.DEGRADED
    assert snap.components[sec].is_group
    assert snap.components[sec].status == Status.DEGRADED

    member = snap.components["gegevens_van_het_lid_met_onmiddellijk_antwoord__beschikbaarheid"]
    assert member.status == Status.MAJOR_OUTAGE
    assert member.raw_status == "Onbeschikbaar"

    partners = snap.components["partners__beschikbaarheid_van_de_diensten_egezondheid"]
    assert partners.status == Status.OPERATIONAL
    # the link row without a status cell is skipped
    assert not any("dashboard_van_de_diensten" in key for key in snap.components)


def test_intermut_french(load_text):
    snap = parse_intermut(load_text("intermut_pharma.html"), "fr")
    comp = snap.components["gegevens_van_het_lid_met_onmiddellijk_antwoord__beschikbaarheid"]
    assert comp.name == "Données du Membre à réponse immédiate – Disponibilité"
    assert comp.raw_status == "Indisponible"


# --- registry / helpers ----------------------------------------------------


def test_build_sources_all_topics():
    sources = build_sources(list(TOPICS), ["pharma", "nurses"], "nl")
    assert list(sources) == [
        "ehealth",
        "careconnect",
        "itsme",
        "nmvs",
        "rijksregister",
        "mycarenet_pharma",
        "mycarenet_nurses",
    ]
    for source in sources.values():
        assert source["provider"] in PROVIDERS
        build_provider(source["provider"], source["params"])  # must not raise
    assert sources["mycarenet_pharma"]["title"] == "MyCareNet apothekers"
    assert sources["ehealth"]["params"] == {"language": "nl"}


def test_build_sources_subset_and_french():
    sources = build_sources(["itsme", "rijksregister"], [], "fr")
    assert list(sources) == ["itsme", "rijksregister"]
    assert sources["rijksregister"]["title"] == "Registre national"
    # MyCareNet ticked without sectors yields nothing (the flow asks for at least one)
    assert build_sources(["mycarenet"], [], "nl") == {}


def test_default_selection(load_json):
    nmvs = default_selection("nmvs", parse_arvato(load_json("arvato_services.json")))
    assert sorted(nmvs) == ["belgium-api-cer", "belgium-sg", "belgium-ws"]
    eh = default_selection("ehealth", parse_ehealth(load_json("ehealth_components.json"), "nl"))
    assert eh and all(cid.startswith("group:") for cid in eh)
    itsme = default_selection("itsme", parse_statuspage(load_json("statuspage_summary.json")))
    assert len(itsme) == 8


def test_parse_datetime():
    assert parse_datetime("2026-11-10 12:30:00.278").minute == 30
    assert parse_datetime("2026-11-10T11:25:00Z").tzinfo is not None
    assert parse_datetime("garbage") is None
    assert parse_datetime(None) is None


def test_display_order_follows_page_numbers(load_json):
    from custom_components.be_health_status.models import Component
    from custom_components.be_health_status.providers import ordered_for_display

    snap = parse_ehealth(load_json("ehealth_components.json"), "nl")
    for n in (10, 3):  # extra numbered groups that would sort wrongly as text
        snap.components[f"group:x{n}"] = Component(
            id=f"group:x{n}", name=f"Extra {n}", status=Status.OPERATIONAL, is_group=True, position=n
        )
    order = [(c.name, member) for c, member in ordered_for_display(snap)]
    groups = [name for name, member in order if not member]
    assert groups == ["IAM", "Coding service", "Extra 3", "Extra 10", "WebService", "Web Application"]
    # services follow their own group, by page position (Vitalink Gateway 9 before Recip-e Patient 12)
    i = order.index(("WebService", False))
    assert order[i + 1 : i + 3] == [("Vitalink Gateway", True), ("Recip-e Patient", True)]


@pytest.mark.parametrize(
    ("full", "short", "number"),
    [
        ("1. IAM - Identity & Access Management", "IAM", 1),
        ("3. TimeStamping service - Preservation of proof of the existence of a document", "TimeStamping service", 3),
        ("4. End to end Encryption (E2EE)", "End to end Encryption (E2EE)", 4),
        (
            "9. Services for managing access to patient's medical data - MetaHub, Consent & Therapeutic Links webservices",  # noqa: E501
            "MetaHub, Consent & Therapeutic Links webservices",
            9,
        ),
        ("10. CoBRHA+ - Common Base Registry for HealthCare Actor", "CoBRHA+", 10),
        ("13. UPPAD (Unique Portal for Profesionals for Administrative Data)", "UPPAD", 13),
        ("18. De geneesmiddelendatabank SAM v2", "De geneesmiddelendatabank SAM v2", 18),
        ("WebService", "WebService", None),
    ],
)
def test_short_group_name(full, short, number):
    from custom_components.be_health_status.providers.ehealth import short_group_name

    assert short_group_name(full) == (short, number)


def test_interventions(load_text):
    from custom_components.be_health_status.providers.ehealth_events import parse_interventions

    events = {e.id: e for e in parse_interventions(load_text("ehealth_home.html"))}
    assert "old1" not in events  # closed
    io300 = events["fR8f0KEB1-y7A1ceTyM6"]
    assert io300.kind == "maintenance"
    assert io300.business_impact is True
    assert io300.starts_at.isoformat() == "2026-11-14T20:00:00+01:00"
    assert io300.ends_at.isoformat() == "2026-11-14T23:00:00+01:00"
    assert io300.url == "https://www.status.ehealth.fgov.be/nl/intervention/fR8f0KEB1-y7A1ceTyM6"
    assert io300.details["partner"] == "CIN-NIC"
    assert io300.details["impact"] == (
        "Admission Management (Async): under_maintenance; Chapter IV (Ask): under_maintenance; "
        "Tarification: under_maintenance"
    )
    multi = events["multi"]
    assert multi.business_impact is False
    assert multi.ends_at.isoformat() == "2026-11-12T23:00:00+01:00"
    assert multi.details["scope"] is None
    night = events["night"]  # 22:00 - 02:00 crosses midnight
    assert night.ends_at.isoformat() == "2026-11-30T02:00:00+01:00"
    assert night.details["impact"] == "Recip-e; PSS"

    cin = parse_interventions(load_text("ehealth_home.html"), partners={"CIN-NIC"})
    assert [e.id for e in cin] == ["fR8f0KEB1-y7A1ceTyM6"]


def test_interventions_missing():
    from custom_components.be_health_status.providers.ehealth_events import parse_interventions

    with pytest.raises(ProviderError):
        parse_interventions("<html><body>no calendar</body></html>")


def test_incidents(load_text):
    from datetime import datetime

    from custom_components.be_health_status.providers.ehealth_events import parse_incidents

    now = datetime(2026, 11, 13, 10, 0, tzinfo=UTC)
    events = parse_incidents(load_text("ehealth_rss.xml"), now)
    assert len(events) == 1  # solved one and the forgotten one are skipped
    inc = events[0]
    assert inc.name == "Issues impacting the Recip-e services"
    assert inc.status == "Investigating"
    assert inc.kind == "incident"
    assert (
        inc.details["description"] == "There are issues impacting the Recip-e services.; Our teams are investigating."
    )
    assert inc.url.startswith("https://www.status.ehealth.fgov.be/nl/incidents/")


def test_event_timing():
    from datetime import datetime, timedelta

    from custom_components.be_health_status.models import Event

    now = datetime(2026, 11, 14, 21, 0, tzinfo=UTC)
    e = Event(
        id="x", name="x", kind="maintenance", starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=1)
    )
    assert e.is_ongoing(now) and not e.is_over(now)
    assert e.is_over(now + timedelta(hours=2))


def test_topic_of() -> None:
    from custom_components.be_health_status.providers import topic_of

    assert topic_of("mycarenet_pharma") == "mycarenet"
    assert topic_of("ehealth") == "ehealth"
