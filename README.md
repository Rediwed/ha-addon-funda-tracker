# Funda Tracker 🏠

Home Assistant local add-on that scrapes your estimated house value from [Funda Mijn Huis](https://www.funda.nl/mijn-huis/) monthly and tracks it as a sensor.

## What it does

- Logs into Funda with your credentials (headless Chromium via Playwright)
- Extracts the estimated house value ("woningwaarde")
- Stores every monthly value in persistent JSON history
- Calculates month-over-month and year-over-year changes
- Pushes `sensor.funda_house_value` via the Supervisor API
- HA template sensors break out monthly/yearly changes, all-time high/low
- Sends a notification when the value changes
- Runs on schedule inside HA (default: 10th of each month at 10:00)

## Setup

### 1. Deploy the add-on to HA Yellow

From your dev machine:

```bash
cd funda-tracker
cat addon/config.yaml addon/Dockerfile addon/requirements.txt addon/funda_scraper.py addon/run.sh | \
  ssh ha "sudo mkdir -p /config/addons/local/funda-tracker"

# Copy all add-on files
for f in addon/*; do
  cat "$f" | ssh ha "sudo tee /config/addons/local/funda-tracker/$(basename $f) > /dev/null"
done
```

### 2. Install the add-on

1. Go to **Settings → Add-ons → Add-on Store**
2. Click the **⋮** menu (top right) → **Check for updates**
3. Find **Funda Tracker** under **Local add-ons**
4. Click **Install** (builds the Docker image on the Yellow)

### 3. Configure

In the add-on **Configuration** tab, set:

| Option | Description | Default |
|---|---|---|
| `funda_email` | Your Funda account email | |
| `funda_password` | Your Funda account password | |
| `schedule_day` | Day of month to scrape (1–28) | `10` |
| `schedule_hour` | Hour to scrape (0–23) | `10` |

### 4. Install the HA package

The package adds template sensors and a notification automation. Already deployed to your HA at `/config/packages/funda.yaml`.

| Entity | Description |
|---|---|
| `sensor.funda_house_value` | Current estimated value (pushed by add-on) |
| `sensor.funda_maandwijziging` | Monthly change in € |
| `sensor.funda_maandwijziging_pct` | Monthly change in % |
| `sensor.funda_jaarwijziging` | Year-over-year change in € |
| `sensor.funda_jaarwijziging_pct` | Year-over-year change in % |
| `sensor.funda_all_time_high` | Highest recorded value |
| `sensor.funda_all_time_low` | Lowest recorded value |

### 5. Start the add-on

Click **Start** in the add-on page. It will:
1. Run an initial scrape if no data exists for this month
2. Then sleep until the next scheduled day/hour

Check the **Log** tab for output.

## History

Data is stored in the add-on's persistent `/data/history.json`:

```json
{
  "address": "Voorbeeldstraat 42, 1234 AB Plaatsnaam",
  "entries": [
    {
      "date": "2026-04-10",
      "value": 425000,
      "scraped_at": "2026-04-10T10:00:00"
    }
  ]
}
```

## Troubleshooting

If the scraper can't find the value, it saves debug files to `/data/`:
- `debug_*.png` — full-page screenshot
- `debug_*.html` — raw page HTML

Access them via the add-on's file system or SSH into HA.

Common issues:
- **Login fails**: Check credentials, Funda may have added CAPTCHA/2FA
- **No value found**: Page structure changed, check debug screenshot
- **Add-on won't build**: Check the Log tab — Playwright needs enough RAM for Chromium
