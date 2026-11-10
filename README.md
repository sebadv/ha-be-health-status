# BE Health Status 🇧🇪

**Know right away when a service your pharmacy or practice depends on is down — inside Home Assistant.**

[![hassfest](https://github.com/sebadv/ha-be-health-status/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/sebadv/ha-be-health-status/actions/workflows/hassfest.yaml)
[![Tests](https://github.com/sebadv/ha-be-health-status/actions/workflows/tests.yaml/badge.svg)](https://github.com/sebadv/ha-be-health-status/actions/workflows/tests.yaml)

> 🇳🇱 **In het kort:** deze integratie houdt in Home Assistant bij of eHealth, CareConnect, itsme,
> NMVS, het Rijksregister en MyCareNet werken. Je ziet alles op één plek, in gewone woorden
> ("Operationeel", "Storing", …), en je kan een melding krijgen zodra er iets misloopt.
>
> 🇫🇷 **En bref :** cette intégration suit dans Home Assistant l'état d'eHealth, CareConnect, itsme,
> NMVS, du Registre national et de MyCareNet. Tout au même endroit, en mots simples
> (« Opérationnel », « Panne », …), avec une alerte dès qu'un service a un problème.

## Why you would want this

When an electronic prescription won't load, a patient's insurance data doesn't come through or the
medicines scanner refuses a box, the first question is always: *is it us, or is it them?*

Normally you'd check five different status websites, each with its own look and its own words for
"it's broken". This integration checks them for you, every minute, and shows the answer in
Home Assistant:

- 🟢 **Everything works** — no need to call the helpdesk or restart your computer.
- 🟠 **Something is slow or partly down** — you know which service, and since when.
- 🔴 **A service is down** — you get a notification on your phone, before the first customer complains.

## What it keeps an eye on

| Service | What it is for |
|---|---|
| **eHealth** | The government platform behind Recip-e (electronic prescriptions), Vitalink, eHealthBox, login and certificates |
| **CareConnect / Corilus** | Pharmacy and practice software, including tarification, medication monitoring and Helena |
| **itsme** | The login and signing app — including planned maintenance, so you know in advance |
| **NMVS** | The medicines verification system you scan boxes against (falsified medicines directive) |
| **National Register** | The National Register, eID (BELPIC) and civil registry (BAEC) |
| **MyCareNet** | Communication with the health insurers: chapter IV, member data, eAttest, third-party billing… for pharmacists, doctors, dentists or nurses |

You tick the topics you care about, and within each topic the services. Only following Recip-e and
Vitalink? Tick eHealth, then just those two.

## What you see in Home Assistant

Every service you pick shows one of these, in your own language:

| You see | It means |
|---|---|
| **Operational** | Working normally |
| **Maintenance** | Planned or ongoing maintenance |
| **Degraded performance** | Working, but slow or with minor problems |
| **Partial outage** | Part of it doesn't work |
| **Outage** | It doesn't work |
| **Unknown** | The status page itself gives no (recent) information |

Every topic you follow appears as its own device, with on top of that:

- **Overall status** – one line that says how that topic is doing.
- **Problem** – an on/off switch that turns on as soon as something is wrong. Use it to send yourself
  a notification, flash a light, or show a warning on a wall tablet in the pharmacy.
- **Next maintenance** (itsme) – when the next announced maintenance starts.

## Getting started

1. **Install it.** In Home Assistant open *Settings → Marketplace* (or HACS), choose *Add from link*
   and paste `https://github.com/sebadv/ha-be-health-status`. Install **BE Health Status** and restart
   Home Assistant.
2. **Add it.** *Settings → Devices & services → Add integration → BE Health Status*.
3. **Tick what you want to follow** – for example eHealth, NMVS and MyCareNet.
4. **Pick the services of each topic.** You get one short step per topic (for MyCareNet you first choose
   your sector). Sensible choices are already ticked.

Want to follow something else later? Open the integration and click **Configure**: you go through the
same steps, with your current choices filled in.

## Get a message when something breaks

This automation sends a notification to your phone when eHealth has a problem, and tells you which
service it is:

```yaml
triggers:
  - trigger: state
    entity_id: binary_sensor.ehealth_problem
    to: "on"
actions:
  - action: notify.notify
    data:
      title: eHealth has a problem
      message: "{{ state_attr('binary_sensor.ehealth_problem', 'affected') | join(', ') }}"
```

## Good to know

- The integration only **reads** public status pages. It never logs in anywhere and needs no passwords.
- It reports what the service providers publish. If they haven't noticed a problem yet, neither has
  this integration.
- The National Register and MyCareNet don't offer a proper data feed, so the integration reads their
  web page. If they redesign it, that source may need an update.

<details>
<summary><b>Technical details</b></summary>

| Source | Read from |
|---|---|
| eHealth | `status.ehealth.fgov.be/{nl,fr}/api/components/prod` (JSON) — services plus the 18 groups; a group shows the worst status of its services |
| CareConnect (PagerDuty status page) | `/api/services`, `/api/impacted_services`, `/api/post_enums` |
| itsme (Statuspage.io) | `/api/v2/summary.json`, including open incidents and scheduled maintenance |
| NMVS | `status-nmvs.arvato-systems.de/api/services` (per country, per endpoint); stale data is reported as unknown |
| National Register | the service status block on `ibz.rrn.fgov.be` |
| MyCareNet | `dashboard.intermut.be/?sector=…` (pharma, doctors, dentists, nurses) |

- States: `operational`, `maintenance`, `degraded`, `partial_outage`, `major_outage`, `unknown`
  (enum sensor, translated in English, Dutch and French). The source's own wording is in the
  `raw_status` attribute.
- Added once; every followed topic (and every MyCareNet sector) is a device with: a status sensor per selected service, `Overall status`,
  `Problem` (binary sensor, attributes `affected` and `incidents`), and `Next maintenance` for
  itsme.
- Polls every minute, 30 s timeout. No extra Python requirements. Works on Home Assistant 2025.8 and
  newer (uses `probatio` on 2026.11+, `voluptuous` before).
- Manual install: copy `custom_components/be_health_status` to your `config/custom_components` folder.

</details>
