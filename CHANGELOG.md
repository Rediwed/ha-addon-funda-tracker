# Changelog

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
