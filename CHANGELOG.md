# Changelog

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
