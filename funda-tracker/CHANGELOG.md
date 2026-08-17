# Changelog

## 1.0.4 (2026-08-17)
- Run one immediate validation scrape on the first start after every add-on update, so an update can repair stale data without waiting for the randomized monthly window
- Persist the new version marker before scraping to prevent crash loops; failed validation scrapes return to the normal six-hour daytime retry schedule

## 1.0.3 (2026-08-17)
- Add the changelog to the add-on package so Home Assistant Supervisor displays release notes before updating
- Keep the legacy `schedule_hour` option schema-compatible during upgrades while clearly logging that randomized daytime scheduling replaces it
- Replan the persisted monthly fetch when `schedule_day` changes
- Require a manual update when crossing the 1.0.2 scheduler and entity-publication migration

## 1.0.2 (2026-08-17)
- Follow Funda's current OIDC/PKCE sign-in route instead of the removed `/mijn/inloggen/` endpoint
- Fetch one day after the configured publication day at a persistent randomized time, using a truncated normal distribution between 09:00 and 21:00
- Retry failed scrapes after at least 6 hours within the daytime window instead of waiting until the next monthly schedule
- Create one persistent Home Assistant notification when a scrape fails and dismiss it automatically after recovery
- Retry immediately when the add-on is manually restarted within 10 minutes while a scrape failure is pending
- Warn once in Home Assistant when shared sensor data is missing, unreadable, or more than 35 days old
- Keep the last valid sensor values available after a failed scrape and expose `last_successful_update` plus `update_overdue` on the house-value entity
- Restrict authentication form submissions and redirects to trusted HTTPS Funda hosts and avoid logging the full property address
- Publish sensor data exclusively through the persistent custom integration instead of transient REST-created entities
- Migrate the optional package and dashboard templates to `sensor.funda_tracker_*`
- Import historical statistics under the persistent `sensor.funda_tracker_*` entity IDs

## 1.0.1 (2026-05-15)
- Detect 404 from Waardecheck API and log a clear message telling the user to configure their house on Funda Mijn Huis first

## 1.0.0 (2026-04-22)
- **Custom integration** (`custom_components/funda_tracker/`) with `RestoreEntity` — sensors persist across HA restarts
- Add-on now writes sensor data to `/share/funda_tracker/sensors.json` for the integration to read
- 12 sensors grouped under a single "Funda Tracker" device in HA
- Config flow with Dutch + English translations
- HACS-ready: publishable as both add-on repository and custom integration
- Add-on `/share` directory mapping added to config

## 0.9.6 (2026-04-15)
- Increase sensor push timeout from 10s to 30s to fix timeouts on HA Yellow
- Add retry logic (3 attempts with backoff) for sensor pushes

## 0.9.5 (2026-04-07)
- Push 12 individual sensors directly from scraper (no package needed for core sensors)
- HA package now optional — only needed for finance sensors + automations
- Package slimmed from 350 to 234 lines
- Sensors auto-created on add-on start: value, bounds, changes, all-time, confidence, price/m², delta

## 0.9.4 (2026-04-07)
- Import statistics for bounds sensors (ondergrens/bovengrens) so ApexCharts shows full history
- Fix dashboard markdown card (table → list format)
- Fix ApexCharts card: use statistics mode for long-term data

## 0.9.3 (2026-04-07)
- Split finance tracking: market gain (vs purchase price) + total profit (vs total investment)
- New helpers: Totale Investering (purchase + renovation + loans + cash)
- Sensors: funda_marktwinst, funda_markt_roi, funda_totale_winst, funda_totale_roi
- Yearly summary includes both market and total ROI
- Removed real name from repository.yaml
- Updated README with finance example and clearer helper docs

## 0.9.2 (2026-04-07)
- Import 12-month history into HA long-term statistics (recorder.import_statistics)
- Push building details, confidence, bounds, neighbourhood to sensor attributes
- HA package: 14 template sensors, 4 input helpers, 4 automations
- Dashboard YAML with ApexCharts history graph
- Finance sensors: overwaarde, winst, ROI (set purchase price in Helpers)
- Updated README with full entity/helper documentation

## 0.9.0 (2026-04-06)
- Initial working release
- curl_cffi Chrome TLS impersonation (bypasses anti-bot)
- OIDC login via login.funda.nl
- Waardecheck API: /v2/estimates + /v1/homes
- Monthly scheduling, JSON history, HA sensor push

- Logs into Funda via OIDC (login.funda.nl) using curl_cffi Chrome TLS impersonation
- Fetches house value + 12-month history from Waardecheck API (`/v2/estimates`)
- Fetches address + building details from `/v1/homes`
- Imports all available historical data on first run
- Pushes `sensor.funda_house_value` to HA via Supervisor API
- Monthly scheduling (configurable day/hour)
- JSON history storage with deduplication
- Stats: monthly/yearly change, all-time high/low
- HA package with template sensors for change tracking + notification automation

<!-- Keep this file in sync with funda-tracker/CHANGELOG.md. -->
