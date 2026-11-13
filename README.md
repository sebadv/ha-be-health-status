<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/logo-dark.png">
    <img src="docs/logo.png" alt="BE Health Status" height="96">
  </picture>
</p>

# BE Health Status 🇧🇪

**Know right away when a service your pharmacy or practice depends on is down — inside Home Assistant.**

[![hassfest](https://github.com/sebadv/ha-be-health-status/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/sebadv/ha-be-health-status/actions/workflows/hassfest.yaml)
[![Release](https://img.shields.io/github/v/release/sebadv/ha-be-health-status)](https://github.com/sebadv/ha-be-health-status/releases)
[![Marketplace: custom repository](https://img.shields.io/badge/Marketplace-custom_repository-41BDF5)](#getting-started)
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
"it's broken". This integration checks them for you, every few minutes, and shows the answer in
Home Assistant:

- 🟢 **Everything works** — no need to call the helpdesk or restart your computer.
- 🟠 **Something is slow or partly down** — you know which service, and since when.
- 🔴 **A service is down** — you get a notification on your phone, before the first customer complains.

## What it keeps an eye on

| Service | What it is for |
|---|---|
| **eHealth** | The government platform behind Recip-e (electronic prescriptions), Vitalink, eHealthBox, login and certificates — including its incidents and the maintenance calendar |
| **CareConnect / Corilus** | Pharmacy and practice software, including tarification, medication monitoring and Helena |
| **itsme** | The login and signing app — including planned maintenance, so you know in advance |
| **NMVS** | The medicines verification system you scan boxes against (falsified medicines directive) |
| **National Register** | The National Register, eID (BELPIC) and civil registry (BAEC) |
| **MyCareNet** | Communication with the health insurers: chapter IV, member data, eAttest, third-party billing… for pharmacists, doctors, dentists or nurses — including announced maintenance |

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
- **Next maintenance** (eHealth, MyCareNet, itsme) – when the next announced maintenance that affects
  users starts, with what it is about and a link. While such maintenance is going on, the overall status
  shows *Maintenance*.

When eHealth publishes an incident ("Investigating"), the **Problem** sensor turns on with the explanation
and a link, even before the service itself is marked as down.

If a source can't be read for two hours (the site is down, or its page was redesigned), you get a
message under *Settings → Repairs*. It disappears by itself when the source answers again.

## Getting started

1. **Install it.** In Home Assistant open *Settings → Marketplace* (or HACS), choose *Add from link*
   and paste `https://github.com/sebadv/ha-be-health-status`. Install **BE Health Status** and restart
   Home Assistant.
2. **Add it.** *Settings → Devices & services → Add integration → BE Health Status*.
3. **Tick what you want to follow** – for example eHealth, NMVS and MyCareNet – and choose whether
   the services should be named in **Dutch or French** (most providers only use those two).
4. **Pick the services of each topic.** You get one short step per topic (for MyCareNet you first choose
   your sector). Sensible choices are already ticked.

Want to follow something else later? Open the integration and click **Configure** → **What I follow**:
you go through the same steps, with your current choices filled in. Switching the language there keeps
the services you ticked.

Want updates faster or less often? **Configure** → **How often it checks** lets you set the number of
minutes per topic (at least 1). The values already filled in are the recommended ones.

## Removing the integration

1. *Settings → Devices & services → BE Health Status* → the three dots → **Delete**.
   All its devices and sensors are removed with it.
2. To remove the files too: *Settings → Marketplace* (or HACS) → **BE Health Status** → **Remove**,
   then restart Home Assistant.

Want to stop following just one topic instead? Use **Configure** and untick it: its device and sensors
are cleaned up automatically.

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

## Something wrong?

[Open an issue](https://github.com/sebadv/ha-be-health-status/issues/new/choose) and attach the
diagnostics file (*Settings → Devices & services → BE Health Status → ⋮ → Download diagnostics*).
It only contains public status information.

## Good to know

- The integration only **reads** public status pages. It never logs in anywhere and needs no passwords.
- By default it checks every 2 minutes (every 5 minutes for the National Register and MyCareNet web
  pages, every 10 minutes for the eHealth maintenance calendar), so it stays light on the providers'
  servers. You can change this under **Configure** (minimum 1 minute).
- It reports what the service providers publish. If they haven't noticed a problem yet, neither has
  this integration.
- The National Register and MyCareNet don't offer a proper data feed, so the integration reads their
  web page. If they redesign it, that source may need an update.

<details>
<summary><b>Technical details</b></summary>

| Source | Read from |
|---|---|
| eHealth | `status.ehealth.fgov.be/{nl,fr}/api/components/prod` (JSON) — services plus the 18 groups (short names; the full name is in `full_name`); a group shows the worst status of its services. Maintenance from the `data-interventions` calendar on `www.status.ehealth.fgov.be`, incidents from its RSS feed |
| CareConnect (PagerDuty status page) | `/api/services`, `/api/impacted_services`, `/api/post_enums` |
| itsme (Statuspage.io) | `/api/v2/summary.json`, including open incidents and scheduled maintenance |
| NMVS | `status-nmvs.arvato-systems.de/api/services` (per country, per endpoint); stale data is reported as unknown |
| National Register | the service status block on `ibz.rrn.fgov.be` |
| MyCareNet | `dashboard.intermut.be/?sector=…` (pharma, doctors, dentists, nurses); maintenance: CIN-NIC interventions on the eHealth calendar |

- States: `operational`, `maintenance`, `degraded`, `partial_outage`, `major_outage`, `unknown`
  (enum sensor, translated in English, Dutch and French). The source's own wording is in the
  `raw_status` attribute.
- Added once; every followed topic (and every MyCareNet sector) is a device with: a status sensor per selected service, `Overall status`,
  `Problem` (binary sensor, attributes `affected` and `incidents`), and `Next maintenance` for
  eHealth, MyCareNet and itsme.
- Polls every 2 minutes by default (5 for HTML pages, 10 for the eHealth calendar), configurable per topic in the options flow (1–1440 min); 30 s timeout; repair issue after 2 hours of failures. When none of the sources answers at start-up, Home Assistant retries
  the setup later; when only some fail, the others keep working.
- *Download diagnostics* on the integration shows the raw answer of every source.
- No extra Python requirements. Works on Home Assistant 2025.8 and
  newer (uses `probatio` on 2026.11+, `voluptuous` before).
- Manual install: copy `custom_components/be_health_status` to your `config/custom_components` folder.

</details>
