"""Constants for the Funda Tracker integration."""

from datetime import timedelta

DOMAIN = "funda_tracker"
SENSOR_DATA_PATH = "/share/funda_tracker/sensors.json"
SCAN_INTERVAL_MINUTES = 30
STALE_DATA_AFTER = timedelta(days=35)

# (storage key, entity name, icon)
FINANCE_INPUTS = [
    ("purchase_price", "Aankoopprijs", "mdi:cash"),
    ("total_investment", "Totale investering", "mdi:cash-multiple"),
    ("mortgage_balance", "Hypotheek", "mdi:bank"),
]

# (unique_id suffix, entity name, unit, icon, required finance input)
FINANCE_SENSORS = [
    ("overwaarde", "Overwaarde", "EUR", "mdi:piggy-bank", "mortgage_balance"),
    ("marktwinst", "Marktwinst", "EUR", "mdi:trending-up", "purchase_price"),
    ("markt_roi", "Markt ROI", "%", "mdi:percent", "purchase_price"),
    ("totale_winst", "Totale winst", "EUR", "mdi:cash-multiple", "total_investment"),
    ("totale_roi", "Totale ROI", "%", "mdi:chart-areaspline", "total_investment"),
]
