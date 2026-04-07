#!/usr/bin/env python3
"""
Funda.nl house value tracker for Home Assistant add-on.

Logs into Funda, calls the Waardecheck API for the current house value
and history, pushes sensor state to HA via Supervisor API.

Uses curl_cffi for Chrome TLS fingerprint impersonation to bypass anti-bot.
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, unquote

from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("FUNDA_DATA_DIR", "/data"))
HISTORY_FILE = DATA_DIR / "history.json"

FUNDA_BASE = "https://www.funda.nl"
FUNDA_LOGIN_START = f"{FUNDA_BASE}/mijn/inloggen/"
FUNDA_MIJN_HUIS = f"{FUNDA_BASE}/mijn-huis/"
WAARDECHECK_API = "https://waardecheck.funda.io/api"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_options():
    options_path = DATA_DIR / "options.json"
    if not options_path.exists():
        log.error("No options.json found -- add-on not configured.")
        sys.exit(1)
    with open(options_path) as f:
        opts = json.load(f)
    log.info("Options loaded (email: %s)", opts.get("funda_email", "?")[:3] + "***")
    return opts


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def create_session():
    session = cffi_requests.Session(impersonate="chrome")
    session.headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    })
    return session


def login(session, email, password):
    """Login to Funda via OIDC flow. Returns True on success."""
    # Step 1: Get login page (Funda redirects to login.funda.nl)
    log.info("[1/4] Getting login page...")
    resp = session.get(FUNDA_LOGIN_START, allow_redirects=True)
    if resp.status_code != 200:
        log.error("  Failed to load login page: %d", resp.status_code)
        return False

    # Step 2: Parse and submit login form
    log.info("[2/4] Submitting credentials...")
    soup = BeautifulSoup(resp.text, "html.parser")
    form = soup.find("form")
    if not form:
        log.error("  No login form found on page")
        return False

    parsed = urlparse(resp.url)
    form_base = f"{parsed.scheme}://{parsed.netloc}"
    action = form.get("action", "")
    form_url = form_base + action if action.startswith("/") else (action if action.startswith("http") else resp.url)

    form_data = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if name and inp.get("type", "").lower() != "submit":
            form_data[name] = inp.get("value", "")

    form_data["UserName"] = email
    form_data["Password"] = password

    resp = session.post(form_url, data=form_data, allow_redirects=True)
    log.info("  Post-login: %d %s", resp.status_code, resp.url[:80])

    # Step 3: Follow OIDC form_post callbacks
    log.info("[3/4] Following OIDC redirects...")
    resp = _follow_oidc_redirects(session, resp)

    # Step 4: Visit Mijn Huis to finalize session
    log.info("[4/4] Establishing session...")
    resp = session.get(FUNDA_MIJN_HUIS, allow_redirects=True)

    token = _get_token(session)
    if not token:
        log.error("  No auth token after login -- credentials may be wrong.")
        return False

    log.info("Login successful!")
    return True


def _follow_oidc_redirects(session, resp, max_hops=5):
    """Follow auto-submitting hidden forms (OIDC form_post callbacks)."""
    for i in range(max_hops):
        soup = BeautifulSoup(resp.text, "html.parser")
        form = soup.find("form")
        if not form:
            break

        inputs = form.find_all("input")
        visible = [inp for inp in inputs if inp.get("type", "").lower() not in ("hidden", "submit")]
        if visible:
            break  # Real form, not auto-submit

        hidden = {inp.get("name"): inp.get("value", "") for inp in inputs
                  if inp.get("name") and inp.get("type", "").lower() == "hidden"}
        if not hidden:
            break

        action = form.get("action", "")
        if not action:
            break

        if action.startswith("/"):
            p = urlparse(resp.url)
            action = f"{p.scheme}://{p.netloc}{action}"

        log.info("  OIDC redirect %d -> %s", i + 1, action[:80])
        resp = session.post(action, data=hidden, allow_redirects=True)

    return resp


def _get_token(session):
    """Extract the OIDC access token from session cookies."""
    return unquote(session.cookies.get("funda.shell.oidc.token", "")) or None


# ---------------------------------------------------------------------------
# Waardecheck API
# ---------------------------------------------------------------------------

def fetch_waardecheck(session):
    """Fetch house value + history from the Waardecheck API."""
    token = _get_token(session)
    if not token:
        log.error("No auth token available.")
        return None

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Origin": "https://www.funda.nl",
        "Referer": "https://www.funda.nl/mijn-huis/",
    }

    # Get valuation data (v2 has history + current estimate)
    log.info("Fetching Waardecheck from API...")
    resp = session.get(f"{WAARDECHECK_API}/v2/estimates", headers=headers)
    if resp.status_code != 200:
        log.error("  v2/estimates failed: %d", resp.status_code)
        return None

    estimates = resp.json()
    log.info("  Got estimate: EUR %s (range EUR %s - EUR %s)",
             f"{estimates['currentEstimate']['value']:,}",
             f"{estimates['currentEstimate']['lowerBound']:,}",
             f"{estimates['currentEstimate']['upperBound']:,}")

    # Get home info (address, building details)
    resp = session.get(f"{WAARDECHECK_API}/v1/homes", headers=headers)
    home = resp.json() if resp.status_code == 200 else {}

    return {
        "estimates": estimates,
        "home": home,
    }


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            data = json.load(f)
        log.info("History loaded: %d entries", len(data.get("entries", [])))
        return data
    log.info("No history -- starting fresh")
    return {"entries": []}


def save_history(history):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    log.info("History saved (%d entries)", len(history.get("entries", [])))


def update_history(history, api_data):
    """Import current + historical data from the API response."""
    estimates = api_data["estimates"]
    home = api_data.get("home", {})
    addr = home.get("address", {})

    if addr:
        history["address"] = f"{addr.get('street', '')} {addr.get('houseNumber', '')}, {addr.get('postalCode', '')} {addr.get('city', '')}"

    # Import history from API
    imported = 0
    for h in estimates.get("history", []):
        date = h.get("date", "")[:10]
        month = date[:7]
        existing = [e for e in history["entries"] if e["date"][:7] == month]
        if not existing:
            history["entries"].append({
                "date": date,
                "value": h["value"],
                "lower_bound": h.get("lowerBound"),
                "upper_bound": h.get("upperBound"),
                "source": "api_history",
                "scraped_at": datetime.now().isoformat(),
            })
            imported += 1

    if imported:
        log.info("Imported %d historical entries from API", imported)

    # Add/update current month
    current = estimates["currentEstimate"]
    now = datetime.now().strftime("%Y-%m-%d")
    month = now[:7]

    for i, e in enumerate(history["entries"]):
        if e["date"][:7] == month:
            history["entries"][i] = {
                "date": now,
                "value": current["value"],
                "lower_bound": current.get("lowerBound"),
                "upper_bound": current.get("upperBound"),
                "source": "api_current",
                "scraped_at": datetime.now().isoformat(),
            }
            break
    else:
        history["entries"].append({
            "date": now,
            "value": current["value"],
            "lower_bound": current.get("lowerBound"),
            "upper_bound": current.get("upperBound"),
            "source": "api_current",
            "scraped_at": datetime.now().isoformat(),
        })

    history["entries"].sort(key=lambda e: e["date"])
    return history


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def calculate_stats(history, current_value):
    entries = sorted(history.get("entries", []), key=lambda e: e["date"])
    stats = {
        "current_value": current_value,
        "previous_value": None,
        "monthly_change": None,
        "monthly_change_pct": None,
        "yearly_change": None,
        "yearly_change_pct": None,
        "all_time_high": current_value,
        "all_time_low": current_value,
        "total_entries": len(entries),
    }
    if len(entries) >= 2:
        prev = entries[-2]
        stats["previous_value"] = prev["value"]
        stats["monthly_change"] = current_value - prev["value"]
        if prev["value"] > 0:
            stats["monthly_change_pct"] = round(
                (current_value - prev["value"]) / prev["value"] * 100, 2
            )
    if len(entries) >= 13:
        year_ago = entries[-13]
        stats["yearly_change"] = current_value - year_ago["value"]
        if year_ago["value"] > 0:
            stats["yearly_change_pct"] = round(
                (current_value - year_ago["value"]) / year_ago["value"] * 100, 2
            )
    vals = [e["value"] for e in entries]
    if vals:
        stats["all_time_high"] = max(vals)
        stats["all_time_low"] = min(vals)
    return stats


# ---------------------------------------------------------------------------
# Home Assistant
# ---------------------------------------------------------------------------

def push_to_homeassistant(value, stats, address, delta, home, estimates):
    """Push individual sensors to HA via Supervisor API."""
    import requests as std_requests
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        log.warning("SUPERVISOR_TOKEN not set -- skipping HA push.")
        return False

    log.info("Pushing sensors to Home Assistant...")

    current = estimates.get("currentEstimate", {})
    bld = home.get("buildingDetail", {})
    addr = home.get("address", {})
    floor_size = bld.get("floorSize", 0)

    # Build list of sensors to push
    sensors = [
        # Main value sensor (keeps all attributes for backward compatibility)
        ("sensor.funda_house_value", value, {
            "unit_of_measurement": "EUR",
            "friendly_name": "Funda Woningwaarde",
            "icon": "mdi:home-analytics",
            "state_class": "measurement",
            "address": address or "Onbekend",
            "last_scraped": datetime.now().isoformat(),
            "lower_bound": current.get("lowerBound"),
            "upper_bound": current.get("upperBound"),
            "confidence_level": estimates.get("confidenceLevel"),
            "delta_pct": (delta or {}).get("delta"),
            "delta_status": (delta or {}).get("status"),
            "floor_size": floor_size,
            "plot_size": bld.get("plotSize"),
            "building_type": bld.get("buildingType"),
            "year_of_construction": bld.get("yearOfConstruction"),
            "maintenance_state": bld.get("maintenanceState"),
            "neighbourhood": addr.get("neighbourhood"),
            "city": addr.get("city"),
        }),
        # Bounds
        ("sensor.funda_ondergrens", current.get("lowerBound", 0), {
            "unit_of_measurement": "EUR", "friendly_name": "Funda Ondergrens",
            "icon": "mdi:arrow-collapse-down", "state_class": "measurement",
        }),
        ("sensor.funda_bovengrens", current.get("upperBound", 0), {
            "unit_of_measurement": "EUR", "friendly_name": "Funda Bovengrens",
            "icon": "mdi:arrow-collapse-up", "state_class": "measurement",
        }),
        # Monthly change
        ("sensor.funda_maandwijziging", stats.get("monthly_change", 0), {
            "unit_of_measurement": "EUR", "friendly_name": "Funda Maandwijziging",
            "icon": "mdi:trending-up" if (stats.get("monthly_change") or 0) >= 0 else "mdi:trending-down",
        }),
        ("sensor.funda_maandwijziging_pct", stats.get("monthly_change_pct", 0), {
            "unit_of_measurement": "%", "friendly_name": "Funda Maandwijziging %",
            "icon": "mdi:percent",
        }),
        # Yearly change
        ("sensor.funda_jaarwijziging", stats.get("yearly_change", 0), {
            "unit_of_measurement": "EUR", "friendly_name": "Funda Jaarwijziging",
            "icon": "mdi:chart-line",
        }),
        ("sensor.funda_jaarwijziging_pct", stats.get("yearly_change_pct", 0), {
            "unit_of_measurement": "%", "friendly_name": "Funda Jaarwijziging %",
            "icon": "mdi:percent",
        }),
        # All-time
        ("sensor.funda_all_time_high", stats.get("all_time_high", 0), {
            "unit_of_measurement": "EUR", "friendly_name": "Funda All-Time High",
            "icon": "mdi:arrow-up-bold",
        }),
        ("sensor.funda_all_time_low", stats.get("all_time_low", 0), {
            "unit_of_measurement": "EUR", "friendly_name": "Funda All-Time Low",
            "icon": "mdi:arrow-down-bold",
        }),
        # Confidence
        ("sensor.funda_betrouwbaarheid", estimates.get("confidenceLevel", "Onbekend"), {
            "friendly_name": "Funda Betrouwbaarheid",
            "icon": "mdi:shield-check" if estimates.get("confidenceLevel") == "High" else "mdi:shield-half-full",
        }),
        # Price per m²
        ("sensor.funda_prijs_per_m2", round(value / floor_size) if floor_size > 0 else 0, {
            "unit_of_measurement": "EUR/m²", "friendly_name": "Funda Prijs per m²",
            "icon": "mdi:ruler-square",
        }),
        # Delta status
        ("sensor.funda_delta_status",
         f"{(delta or {}).get('delta', '?')}% {(delta or {}).get('status', '')}" if delta else "Onbekend", {
            "friendly_name": "Funda Delta Status",
            "icon": "mdi:arrow-up" if (delta or {}).get("status") == "Increased" else "mdi:arrow-down",
        }),
    ]

    # Only push change sensors if they have values
    sensors = [(eid, state, attrs) for eid, state, attrs in sensors
               if state is not None]

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    pushed = 0
    for entity_id, state, attrs in sensors:
        # Remove None values from attrs
        clean_attrs = {k: v for k, v in attrs.items() if v is not None}
        try:
            resp = std_requests.post(
                f"http://supervisor/core/api/states/{entity_id}",
                headers=headers,
                json={"state": state, "attributes": clean_attrs},
                timeout=10,
            )
            resp.raise_for_status()
            pushed += 1
        except std_requests.RequestException as exc:
            log.error("Failed to push %s: %s", entity_id, exc)

    log.info("Pushed %d/%d sensors to HA.", pushed, len(sensors))
    return pushed > 0


def import_statistics(estimates):
    """Import historical data into HA's long-term statistics.

    This allows the HA history graph to show past months even though
    the sensor didn't exist yet. Uses recorder.import_statistics.
    Runs on every scrape — HA handles deduplication internally.
    """
    import requests as std_requests
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return False

    history = estimates.get("history", [])
    if not history:
        log.info("No historical data to import into HA statistics.")
        return True

    log.info("Importing %d historical data points into HA statistics...", len(history))

    # Build stats for each data point
    entries = []
    for h in history:
        date_str = h.get("date", "")
        if not date_str:
            continue
        try:
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            ts = dt.strftime("%Y-%m-%dT00:00:00+00:00")
        except ValueError:
            continue
        entries.append({
            "start": ts,
            "value": h["value"],
            "lower": h.get("lowerBound", h["value"]),
            "upper": h.get("upperBound", h["value"]),
        })

    if not entries:
        return True

    # Import stats for main sensor + bounds sensors
    sensors = [
        ("sensor.funda_house_value", "Funda Woningwaarde", [({"start": e["start"], "mean": e["value"], "min": e["lower"], "max": e["upper"]}) for e in entries]),
        ("sensor.funda_ondergrens", "Funda Ondergrens", [{"start": e["start"], "mean": e["lower"], "min": e["lower"], "max": e["lower"]} for e in entries]),
        ("sensor.funda_bovengrens", "Funda Bovengrens", [{"start": e["start"], "mean": e["upper"], "min": e["upper"], "max": e["upper"]} for e in entries]),
    ]

    success = True
    for statistic_id, name, stats in sensors:
        payload = {
            "has_mean": True,
            "has_sum": False,
            "name": name,
            "source": "recorder",
            "statistic_id": statistic_id,
            "unit_of_measurement": "€",
            "stats": stats,
        }
        try:
            resp = std_requests.post(
                "http://supervisor/core/api/services/recorder/import_statistics",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            log.info("Imported %d stats for %s", len(stats), statistic_id)
        except std_requests.RequestException as exc:
            log.error("Statistics import failed for %s: %s", statistic_id, exc)
            success = False

    for e in entries:
        log.info("  %s: EUR %s (EUR %s - EUR %s)", e["start"][:10], f"{e['value']:,}", f"{e['lower']:,}", f"{e['upper']:,}")

    return success


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run():
    log.info("")
    log.info("=" * 60)
    log.info("  FUNDA TRACKER -- Starting scrape")
    log.info("=" * 60)

    options = load_options()
    email = options.get("funda_email", "")
    password = options.get("funda_password", "")

    if not email or not password:
        log.error("Funda credentials not configured!")
        return False

    session = create_session()

    if not login(session, email, password):
        log.error("Login failed!")
        return False

    api_data = fetch_waardecheck(session)
    if not api_data:
        log.error("Failed to fetch Waardecheck data.")
        return False

    estimates = api_data["estimates"]
    current = estimates["currentEstimate"]
    home = api_data.get("home", {})
    addr = home.get("address", {})
    address = f"{addr.get('street', '')} {addr.get('houseNumber', '')}, {addr.get('postalCode', '')} {addr.get('city', '')}" if addr else None

    history = load_history()
    history = update_history(history, api_data)
    save_history(history)

    stats = calculate_stats(history, current["value"])

    # Summary
    log.info("")
    log.info("=" * 60)
    log.info("  RESULTS")
    log.info("  %-24s EUR %s", "Current value:", f"{current['value']:,}")
    log.info("  %-24s EUR %s - EUR %s", "Range:", f"{current.get('lowerBound', 0):,}", f"{current.get('upperBound', 0):,}")
    if address:
        log.info("  %-24s %s", "Address:", address)
    delta = estimates.get("estimateDelta", {})
    if delta:
        log.info("  %-24s %s%% (%s)", "Monthly delta:", delta.get("delta", "?"), delta.get("status", "?"))
    log.info("  %-24s %s", "Confidence:", estimates.get("confidenceLevel", "?"))
    if stats["monthly_change"] is not None:
        log.info("  %-24s EUR %s (%s%%)", "Monthly change:", f"{stats['monthly_change']:+,}", f"{stats['monthly_change_pct']:+.2f}")
    if stats["yearly_change"] is not None:
        log.info("  %-24s EUR %s (%s%%)", "Yearly change:", f"{stats['yearly_change']:+,}", f"{stats['yearly_change_pct']:+.2f}")
    log.info("  %-24s EUR %s", "All-time high:", f"{stats['all_time_high']:,}")
    log.info("  %-24s EUR %s", "All-time low:", f"{stats['all_time_low']:,}")
    log.info("  %-24s %d", "Data points:", stats["total_entries"])
    history_entries = estimates.get("history", [])
    if history_entries:
        log.info("  Historical data from API:")
        for h in history_entries:
            log.info("    %s: EUR %s (EUR %s - EUR %s)", h["date"], f"{h['value']:,}", f"{h.get('lowerBound', 0):,}", f"{h.get('upperBound', 0):,}")
    log.info("=" * 60)

    push_to_homeassistant(current["value"], stats, address, delta, home, estimates)

    # Import historical data into HA long-term statistics
    import_statistics(estimates)

    log.info("")
    log.info("Scrape complete! Next run on day %s.", options.get("schedule_day", 10))
    return True


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
