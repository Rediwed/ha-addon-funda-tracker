# Funda Tracker 🏠

Home Assistant add-on that tracks your house value from [Funda Mijn Huis](https://www.funda.nl/mijn-huis/) and exposes it as a sensor with 12 months of history.

## Features

- Logs into Funda via OIDC and calls the Waardecheck API directly
- Uses `curl_cffi` for Chrome TLS fingerprint impersonation (bypasses anti-bot)
- Current value + confidence level + upper/lower bounds
- 12-month historical data imported into HA long-term statistics
- Monthly scheduling one day after Funda's expected publication date, randomized between 09:00 and 21:00
- Persistent Home Assistant notification on scrape failure, cleared automatically after recovery
- Persistent custom-integration sensors grouped under one Funda Tracker device
- Monthly/yearly change, all-time high/low, price per m², and more
- Finance helpers: purchase price, mortgage balance → equity, profit, ROI
- Automations: monthly notification, threshold alerts, significant change alert, yearly summary

## Installation

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FRediwed%2Fha-addon-funda-tracker)

1. Click the badge above (or in HA, go to **Settings → Add-ons → Add-on Store → ⋮ → Repositories** and add `https://github.com/Rediwed/ha-addon-funda-tracker`)
2. Find **Funda Tracker** and click **Install**
3. Install the custom integration through HACS (add this repository as category **Integration**) or copy `custom_components/funda_tracker` to `/config/custom_components/funda_tracker`
4. Restart Home Assistant, then add **Funda Tracker** under **Settings → Devices & services**
5. Open the add-on **Configuration** tab and enter your Funda email + password
6. Start the add-on; it writes shared data that the integration exposes as persistent sensors
7. *(Optional)* For finance tracking + automations: copy `ha/packages/funda.yaml` to `/config/packages/funda.yaml` and reload YAML

## Configuration

| Option | Description | Default |
|---|---|---|
| `funda_email` | Your Funda account email | |
| `funda_password` | Your Funda account password | |
| `schedule_day` | Expected day of the month on which Funda publishes new data (1–28) | `10` |

The add-on fetches the data on the following calendar day. It chooses a new time
for each publication month from a truncated normal distribution centred on
15:00 with a 3-hour standard deviation and hard limits of 09:00 and 21:00. The
selected time is saved in `/data`, so restarting the add-on does not redraw it.

When upgrading from 1.0.1, the old `schedule_hour` value remains accepted for
configuration compatibility but is ignored. Home Assistant requires manual
confirmation for this update because `schedule_day` now means Funda's expected
publication day, the randomized fetch runs one day later, and consumers must use
the persistent `sensor.funda_tracker_*` entities.

## Entities

### Sensors (provided by the custom integration)

| Entity | Description |
|---|---|
| `sensor.funda_tracker_woningwaarde` | Current estimated value with all data as attributes |
| `sensor.funda_tracker_ondergrens` | Lower bound of estimate range |
| `sensor.funda_tracker_bovengrens` | Upper bound of estimate range |
| `sensor.funda_tracker_maandwijziging` | Monthly change in € |
| `sensor.funda_tracker_maandwijziging_2` | Monthly change in % |
| `sensor.funda_tracker_jaarwijziging` | Year-over-year change in € |
| `sensor.funda_tracker_jaarwijziging_2` | Year-over-year change in % |
| `sensor.funda_tracker_all_time_high` | Highest recorded value |
| `sensor.funda_tracker_all_time_low` | Lowest recorded value |
| `sensor.funda_tracker_betrouwbaarheid` | Confidence level (High/Medium/Low) |
| `sensor.funda_tracker_prijs_per_m2` | Value per square meter |
| `sensor.funda_tracker_delta_status` | Monthly delta percentage + direction |

The main `sensor.funda_tracker_woningwaarde` entity keeps its last valid value
when a scrape fails. Its `last_successful_update` attribute records when fresh
data was last published, while `update_overdue` becomes `true` after 35 days.
These are attributes because they describe the freshness of the valuation; a
separate entity is not required for the built-in failure notification.

### Finance sensors (requires optional HA package)

| Entity | Description |
|---|---|
| `sensor.funda_overwaarde` | Equity (value − mortgage) |
| `sensor.funda_marktwinst` | Market gain (value − purchase price) |
| `sensor.funda_markt_roi` | Market ROI since purchase (%) |
| `sensor.funda_totale_winst` | Total profit (value − total investment) |
| `sensor.funda_totale_roi` | Total ROI including renovations (%) |

### Input helpers

| Helper | Description |
|---|---|
| `input_number.funda_purchase_price` | The price you paid for the house (koopsom) → enables market gain/ROI |
| `input_number.funda_total_investment` | Everything you put in: purchase + renovation + loans + cash → enables total profit/ROI |
| `input_number.funda_mortgage_balance` | Outstanding mortgage balance → enables equity sensor |
| `input_number.funda_value_alert_high` | Get notified when value rises above this |
| `input_number.funda_value_alert_low` | Get notified when value drops below this |

> **Finance example:** You bought a house for €350k, then spent €100k renovation (mortgage), €20k green loan, and €30k cash. Set **Aankoopprijs** = 350000 and **Totale Investering** = 500000. If the current value is €475k: Market ROI = +35.7%, Total ROI = −5.0%.

> **Note:** Finance sensors only appear once you set the corresponding helper to a value > 0. Go to **Settings → Devices & Services → Helpers**.

## Automations (from HA package)

| Automation | Description |
|---|---|
| Monthly notification | Sends a push when the value updates |
| Threshold alerts | Notifies when value crosses your configured high/low limits |
| Significant change | Warns if monthly change exceeds ±2% |
| Yearly summary | Sends a year-in-review summary on January 1st |

## Dashboard

A ready-to-use dashboard is included in this repo. Copy the YAML from GitHub:

👉 **[funda-dashboard.yaml](https://github.com/Rediwed/ha-addon-funda-tracker/blob/main/ha/dashboard/funda-dashboard.yaml)**

### Prerequisites

Install [apexcharts-card](https://github.com/RomRider/apexcharts-card) from HACS for the history graph:
1. Go to **HACS → Frontend → Search "apexcharts-card" → Install**
2. Restart HA

### Option A: Add as a new dashboard

1. Go to **Settings → Dashboards → Add Dashboard**
2. Choose **"New dashboard from scratch"**
3. Give it a name (e.g. "Funda") and click **Create**
4. Open the new dashboard → click **⋮ → Edit Dashboard → ⋮ → Raw configuration editor**
5. Paste the contents of `ha/dashboard/funda-dashboard.yaml`
6. Click **Save**

### Option B: Add cards to an existing dashboard

1. Open your dashboard → click **⋮ → Edit Dashboard → + Add Card**
2. Choose **Manual** (YAML) at the bottom
3. Copy individual cards from `ha/dashboard/funda-dashboard.yaml` and paste them one by one

## How it works

```
Login → /mijn-huis/auth/oidc/signin/ → login.funda.nl (OIDC + PKCE) → session cookies
  ↓
API   → GET /v2/estimates → current value + 12-month history
      → GET /v1/homes → address + building details
  ↓
File  → /share/funda_tracker/sensors.json (atomic write)
  ↓
HA    → Funda Tracker custom integration → sensor.funda_tracker_*
  → recorder.import_statistics (backfill history)

Schedule → publication day + 1 → random daytime target (09:00–21:00)
  → failure: persistent HA notification + retry after at least 6 hours
  → recovery: dismiss notification and schedule the next publication month
```

## Troubleshooting

- **Login fails**: Check credentials and the first failing step in the add-on Log tab
- **No fresh data**: A failed scrape creates a persistent HA notification and retries after at least 6 hours within 09:00–21:00
- **Retry while debugging**: Restart the add-on within 10 minutes while a failure is pending to run one immediate retry, even outside the normal daytime window
- **Old `sensor.funda_*` entities unavailable**: Migrate dashboards, templates, and automations to `sensor.funda_tracker_*`
- **Stale-data warning**: The integration has not received a valid shared data file for more than 35 days
- **Entity remains available after failure**: The last valid valuation stays visible; inspect `last_successful_update` and `update_overdue` on the main entity
- **Profit/ROI empty**: Set your purchase price in Settings → Helpers → Funda Aankoopprijs
- **No history graph**: Install apexcharts-card from HACS
