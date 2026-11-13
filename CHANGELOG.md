# Changelog

Each release in the Marketplace (HACS) shows the section of its version below.
Keep it short: one line per change, written for users.

## 0.6.0

- New: choose the language of the service names (Dutch or French) under **Configure → What I follow**
- Your ticked services stay ticked when you switch language
- Entity IDs do not change

## 0.5.0

- New: set how often each topic is checked under **Configure → How often it checks**
- Minimum 1 minute; recommended values are filled in
- **Configure** now opens a small menu: *What I follow* or *How often it checks*

## 0.4.0

- New: eHealth planned maintenance (sensor *Next maintenance*, with period, scope and impact)
- New: eHealth incidents count as a problem until they are marked *Solved*
- New: MyCareNet maintenance announced by CIN-NIC
- Shorter eHealth names, e.g. *IAM* instead of *1. IAM - Identity & Access Management*
- A repair notice appears when a source has been unreachable for 2 hours
- Lighter polling: 2 min (eHealth, CareConnect, itsme, NMVS), 5 min (National Register, MyCareNet)

## 0.3.0

- *Download diagnostics* on the integration
- Meets the Home Assistant and HACS requirements

## 0.2.2

- Logo and icon

## 0.2.1

- Services listed in natural order, each under its group

## 0.2.0

- Setup with tick boxes per topic, then per service
- Version numbers in the Marketplace instead of build codes

## 0.1.0

- First version: eHealth, CareConnect, itsme, NMVS, National Register and MyCareNet in one integration
