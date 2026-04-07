#!/bin/sh
# run.sh — HA add-on entrypoint
# Always runs a scrape on startup, then sleeps until the scheduled day/hour.

set -e

OPTIONS_FILE="/data/options.json"
VERSION=$(grep '^version:' /app/config.yaml 2>/dev/null | sed 's/version: *"\(.*\)"/\1/' || echo "unknown")
SCHEDULE_DAY=$(python3 -c "import json; print(json.load(open('$OPTIONS_FILE')).get('schedule_day', 10))")
SCHEDULE_HOUR=$(python3 -c "import json; print(json.load(open('$OPTIONS_FILE')).get('schedule_hour', 10))")

echo "============================================================"
echo "  Funda Tracker Add-on v${VERSION}"
echo "  Schedule: day $SCHEDULE_DAY of each month at ${SCHEDULE_HOUR}:00"
echo "============================================================"
echo ""

# Always run on startup to verify login + get immediate data
echo "Running initial scrape on startup..."
python3 /app/funda_scraper.py || echo "Initial scrape failed — will retry on schedule."

# Main loop — check every 30 minutes
while true; do
    CURRENT_DAY=$(date +%-d)
    CURRENT_HOUR=$(date +%-H)

    if [ "$CURRENT_DAY" -eq "$SCHEDULE_DAY" ] && [ "$CURRENT_HOUR" -eq "$SCHEDULE_HOUR" ]; then
        echo ""
        echo "$(date): Scheduled scrape time — running..."
        python3 /app/funda_scraper.py || echo "Scheduled scrape failed."
        # Sleep 23 hours to avoid running twice on the same day
        sleep 82800
    else
        # Check again in 30 minutes
        sleep 1800
    fi
done
