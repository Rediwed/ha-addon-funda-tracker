"""Constants for the Funda Tracker integration."""

from datetime import timedelta

DOMAIN = "funda_tracker"
SENSOR_DATA_PATH = "/share/funda_tracker/sensors.json"
SCAN_INTERVAL_MINUTES = 30
STALE_DATA_AFTER = timedelta(days=35)
