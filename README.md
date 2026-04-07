# Funda Tracker 🏠

Home Assistant add-on that tracks your house value from [Funda Mijn Huis](https://www.funda.nl/mijn-huis/) and exposes it as a sensor with 12 months of history.

## Features

- Logs into Funda via OIDC and calls the Waardecheck API directly
- Uses `curl_cffi` for Chrome TLS fingerprint impersonation (bypasses anti-bot)
- Current value + confidence level + upper/lower bounds
- 12-month historical data imported into HA long-term statistics
- Monthly scheduling (configurable day/hour)
- Template sensors for monthly/yearly change, all-time high/low, price per m², and more
- Finance helpers: purchase price, mortgage balance → equity, profit, ROI
- Automations: monthly notification, threshold alerts, significant change alert, yearly summary

## Installation

1. In HA, go to **Settings → Add-ons → Add-on Store → ⋮ → Repositories**
2. Add: `https://github.com/Rediwed/ha-addon-funda-tracker`
3. Find **Funda Tracker** and click **Install**
4. Go to **Configuration** and enter your Funda email + password
5. Copy `ha/packages/funda.yaml` to `/config/packages/funda.yaml` on your HA
6. Restart HA (or reload Template entities + Input numbers + Automations)
7. **Start** the add-on

## Configuration

| Option | Description | Default |
|---|---|---|
| `funda_email` | Your Funda account email | |
| `funda_password` | Your Funda account password | |
| `schedule_day` | Day of month to scrape (1–28) | `10` |
| `schedule_hour` | Hour to scrape (0–23) | `10` |

## Entities

### Main sensor (pushed by add-on)

| Entity | Description |
|---|---|
| `sensor.funda_house_value` | Current estimated value with all data as attributes |

### Template sensors (from HA package)

| Entity | Description |
|---|---|
| `sensor.funda_maandwijziging` | Monthly change in € |
| `sensor.funda_maandwijziging_pct` | Monthly change in % |
| `sensor.funda_jaarwijziging` | Year-over-year change in € |
| `sensor.funda_jaarwijziging_pct` | Year-over-year change in % |
| `sensor.funda_all_time_high` | Highest recorded value |
| `sensor.funda_all_time_low` | Lowest recorded value |
| `sensor.funda_ondergrens` | Lower bound of estimate range |
| `sensor.funda_bovengrens` | Upper bound of estimate range |
| `sensor.funda_betrouwbaarheid` | Confidence level (High/Medium/Low) |
| `sensor.funda_prijs_per_m2` | Value per square meter |
| `sensor.funda_delta_status` | Monthly delta percentage + direction |
| `sensor.funda_overwaarde` | Equity (value − mortgage) |
| `sensor.funda_winst` | Profit since purchase (value − purchase price) |
| `sensor.funda_roi` | Return on investment since purchase (%) |

### Input helpers

| Helper | Description |
|---|---|
| `input_number.funda_purchase_price` | What you paid for the house — set this to enable profit/ROI sensors |
| `input_number.funda_mortgage_balance` | Outstanding mortgage — set this to enable equity sensor |
| `input_number.funda_value_alert_high` | Get notified when value rises above this |
| `input_number.funda_value_alert_low` | Get notified when value drops below this |

> **Note:** Profit, ROI, and Equity sensors only appear once you set the corresponding input helper to a value > 0. Go to **Settings → Devices & Services → Helpers** or find them on the dashboard.

## Automations (from HA package)

| Automation | Description |
|---|---|
| Monthly notification | Sends a push when the value updates |
| Threshold alerts | Notifies when value crosses your configured high/low limits |
| Significant change | Warns if monthly change exceeds ±2% |
| Yearly summary | Sends a year-in-review summary on January 1st |

## Dashboard

A ready-to-use dashboard YAML is included at `ha/dashboard/funda-dashboard.yaml`. Requires [apexcharts-card](https://github.com/RomRider/apexcharts-card) from HACS for the history graph.

## How it works

```
Login → /mijn/inloggen/ → login.funda.nl (OIDC) → session cookies
  ↓
API   → GET /v2/estimates → current value + 12-month history
      → GET /v1/homes → address + building details
  ↓
HA    → sensor.funda_house_value (Supervisor API)
      → recorder.import_statistics (backfill history)
```

## Troubleshooting

- **Login fails**: Check credentials in add-on Configuration
- **No data**: Check the add-on Log tab for detailed step-by-step output
- **Profit/ROI empty**: Set your purchase price in Settings → Helpers → Funda Aankoopprijs
- **No history graph**: Install apexcharts-card from HACS
