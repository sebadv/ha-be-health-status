# BE Health Status – Home Assistant integration 🇧🇪

[![hassfest](https://github.com/sebadv/ha-be-health-status/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/sebadv/ha-be-health-status/actions/workflows/hassfest.yaml)
[![HACS](https://github.com/sebadv/ha-be-health-status/actions/workflows/hacs.yaml/badge.svg)](https://github.com/sebadv/ha-be-health-status/actions/workflows/hacs.yaml)
[![Tests](https://github.com/sebadv/ha-be-health-status/actions/workflows/tests.yaml/badge.svg)](https://github.com/sebadv/ha-be-health-status/actions/workflows/tests.yaml)

Follow the status of the Belgian healthcare and e-government services that pharmacies,
doctors and their software depend on — in one integration, with one consistent status.

| Source | What you get | How it is read |
|---|---|---|
| **eHealth** (status.ehealth.fgov.be) | ~86 services (Recip-e, Vitalink, IAM, eHealthBox, …) and their 18 groups | official JSON API |
| **CareConnect / Corilus** | CareConnect, Tarification, Medication Monitoring, Helena, Passport, … | PagerDuty status page API |
| **itsme** | every component and component group, open incidents, announced maintenance | Statuspage.io API |
| **NMVS** (medicines verification, Arvato Systems) | Belgium/Luxembourg and other Arvato countries, per endpoint | Arvato status API |
| **National Register** (IBZ) | Rijksregister, BELPIC (eID), BAEC | status block on the IBZ website |
| **MyCareNet** (intermutualistic dashboard) | per sector (pharmacists, doctors, dentists, nurses): availability and response time of each transaction | intermut.be dashboard |
| **Any Statuspage.io page** | add it by URL | Statuspage.io API |
| **Any PagerDuty status page** | add it by URL | PagerDuty status page API |

## Status values

Every sensor uses the same states, whatever the source calls them:

| State | Meaning |
|---|---|
| `operational` | working normally |
| `maintenance` | (planned) maintenance |
| `degraded` | slower or minor issues |
| `partial_outage` | part of the service is down |
| `major_outage` | down |
| `unknown` | the page reports no data, or reports stale data |

The text the page itself shows (e.g. *Operationeel*, *Normaal / Normal*, *Available, but degraded*)
is kept in the `raw_status` attribute. States are translated in the UI (English, Dutch, French).

Groups (eHealth groups, itsme component groups, a MyCareNet table, an NMVS country) get the
**worst** status of the services in them.

## Entities

Each status page you add becomes one device with:

- a **status sensor** for every service you selected
- **Overall status**: the worst status of the selected services
- **Problem** (binary sensor): on when a selected service is not operational or an incident is open —
  handy for notifications; the `affected` and `incidents` attributes say what is wrong
- **Next maintenance** (Statuspage pages such as itsme): when the next announced maintenance starts

## Installation

### Marketplace / HACS

Add this repository as a custom repository (category *Integration*), install **BE Health Status**
and restart Home Assistant.

### Manual

Copy `custom_components/be_health_status` into your `config/custom_components` folder and restart.

## Setup

**Settings → Devices & services → Add integration → BE Health Status**

1. Choose the source.
2. Fill in what it needs (language, sector, or the address for "other" pages).
3. Tick the services to monitor. Use **Configure** on the entry later to change the selection.

Add the integration once per source (and once per sector for MyCareNet).

## Example: notify on a problem

```yaml
triggers:
  - trigger: state
    entity_id: binary_sensor.ehealth_problem
    to: "on"
actions:
  - action: notify.notify
    data:
      title: eHealth problem
      message: "{{ state_attr('binary_sensor.ehealth_problem', 'affected') | join(', ') }}"
```

## Notes

- Polling interval is one minute; requests time out after 30 seconds.
- The National Register and MyCareNet sources read HTML pages; if those sites are redesigned the
  source may stop working until the parser is updated. All other sources use JSON APIs.
- eHealth only publishes status code 1 (operational) in normal operation; other states are recognised
  from the localised status text.
