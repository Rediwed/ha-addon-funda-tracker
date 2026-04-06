#!/bin/sh
# run.sh — HA add-on entrypoint
# Sleeps until the configured day/hour each month, then runs the scraper.
# Also runs once on startup if it hasn't run this month yet.

set -e

OPTIONS_FILE="/data/options.json"
SCHEDULE_DAY=$(python3 -c "import json; print(json.load(open('$OPTIONS_FILE')).get('schedule_day', 10))")
SCHEDULE_HOUR=$(python3 -c "import json; print(json.load(open('$OPTIONS_FILE')).get('schedule_hour', 10))")

echo "=== Funda Tracker Add-on ==="
echo "Schedule: day $SCHEDULE_DAY of each month at ${SCHEDULE_HOUR}:00"

# Check if we already ran this month
should_run_now() {
    HISTORY="/data/history.json"
    CURRENT_MONTH=$(date +%Y-%m)

    if [ ! -f "$HISTORY" ]; then
        echo "No history yet — running initial scrape."
        return 0
    fi

    if python3 -c "
import json, sys
h = json.load(open('$HISTORY'))
entries = h.get('entries', [])
this_month = [e for e in entries if e['date'].startswith('$CURRENT_MONTH')]
sys.exit(0 if not this_month else 1)
"; then
        echo "No entry for $CURRENT_MONTH yet — running scrape."
        return 0
    fi

    echo "Already have data for $CURRENT_MONTH — waiting for next schedule."
    return 1
}

# Run on startup if needed
if should_run_now; then
    python3 /app/funda_scraper.py || echo "Scrape failed — will retry on schedule."
fi

# Main loop — check every hour
while true; do
    CURRENT_DAY=$(date +%-d)
    CURRENT_HOUR=$(date +%-H)

    if [ "$CURRENT_DAY" -eq "$SCHEDULE_DAY" ] && [ "$CURRENT_HOUR" -eq "$SCHEDULE_HOUR" ]; then
        echo "$(date): Scheduled scrape time — running…"
        python3 /app/funda_scraper.py || echo "Scrape failed."
        # Sleep 23 hours to avoid running twice on the same day
        sleep 82800
    else
        # Check again in 30 minutes
        sleep 1800
    fi
done
