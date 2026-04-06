#!/usr/bin/env python3
"""
Funda.nl house value scraper for Home Assistant add-on.

Reads config from /data/options.json (HA add-on options),
uses the Supervisor API to push sensor state,
stores history in /data/history.json.
"""

import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

DATA_DIR = Path("/data")
HISTORY_FILE = DATA_DIR / "history.json"

FUNDA_BASE = "https://www.funda.nl"
FUNDA_LOGIN_URL = f"{FUNDA_BASE}/account/login/"
FUNDA_MIJN_HUIS_URL = f"{FUNDA_BASE}/mijn-huis/"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux aarch64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# Config (HA add-on options)
# ---------------------------------------------------------------------------

def load_options():
    options_path = DATA_DIR / "options.json"
    if not options_path.exists():
        log.error("No options.json found — add-on not configured.")
        sys.exit(1)
    with open(options_path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Scraper (Playwright)
# ---------------------------------------------------------------------------

def scrape_funda(email, password):
    """Launch headless browser, log in to Funda, and return the house value."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(user_agent=USER_AGENT, locale="nl-NL")
        page = context.new_page()

        try:
            # --- Login --------------------------------------------------------
            log.info("Navigating to Funda login…")
            page.goto(FUNDA_LOGIN_URL, wait_until="domcontentloaded")

            _dismiss_cookies(page)

            log.info("Filling login form…")
            page.fill('input[type="email"], input[name="email"], #Email', email)
            page.fill('input[type="password"], input[name="password"], #Password', password)
            page.click('button[type="submit"]')

            page.wait_for_load_state("networkidle", timeout=15_000)

            if "/login" in page.url.lower():
                _save_debug(page, "login_failed")
                log.error("Login failed — still on the login page. Check credentials.")
                return None

            log.info("Login successful (%s)", page.url)

            # --- Mijn Huis ---------------------------------------------------
            log.info("Navigating to Mijn Huis…")
            page.goto(FUNDA_MIJN_HUIS_URL, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=15_000)

            if "/login" in page.url.lower():
                log.error("Redirected to login — session may have expired.")
                return None

            _dismiss_cookies(page)
            page.wait_for_timeout(3000)

            # --- Extract value ------------------------------------------------
            value = _extract_value(page)
            address = _extract_address(page)

            if value is None:
                _save_debug(page, "no_value")
                log.error("Could not find house value. Debug screenshot + HTML saved.")
                return None

            return {
                "value": value,
                "address": address,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "scraped_at": datetime.now().isoformat(),
            }

        except PlaywrightTimeout as exc:
            _save_debug(page, "timeout")
            log.error("Timeout during scraping: %s", exc)
            return None
        finally:
            browser.close()


def _dismiss_cookies(page):
    for selector in [
        'button:has-text("Accepteren")',
        'button:has-text("Alles accepteren")',
        'button:has-text("Accept")',
        "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
        '[data-testid="accept-cookies"]',
    ]:
        try:
            page.click(selector, timeout=3000)
            log.debug("Dismissed cookie banner via %s", selector)
            return
        except PlaywrightTimeout:
            continue


def _extract_value(page):
    price_re = re.compile(r"€\s*([\d.]+(?:\.\d{3})*)")

    body_text = page.inner_text("body")
    matches = price_re.findall(body_text)
    for match_str in matches:
        candidate = int(match_str.replace(".", ""))
        if 50_000 < candidate < 10_000_000:
            log.info("Found value via text search: €%s", f"{candidate:,}")
            return candidate

    for selector in [
        '[data-test-id*="value"]',
        '[data-testid*="value"]',
        '[class*="waarde"]',
        '[class*="value"]',
        '[class*="price"]',
    ]:
        try:
            elements = page.query_selector_all(selector)
            for el in elements:
                text = el.inner_text()
                m = price_re.search(text)
                if m:
                    candidate = int(m.group(1).replace(".", ""))
                    if 50_000 < candidate < 10_000_000:
                        log.info("Found value via selector '%s': €%s", selector, f"{candidate:,}")
                        return candidate
        except Exception:
            continue

    return None


def _extract_address(page):
    addr_re = re.compile(r"[A-Z][a-z]+\S*\s+\d+\s*\w?,?\s*\d{4}\s*[A-Z]{2}")
    body_text = page.inner_text("body")
    m = addr_re.search(body_text)
    return m.group(0).strip() if m else None


def _save_debug(page, label):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = DATA_DIR / f"debug_{label}_{ts}.png"
    html_path = DATA_DIR / f"debug_{label}_{ts}.html"
    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
        html_path.write_text(page.content())
        log.info("Debug files saved: %s, %s", screenshot_path, html_path)
    except Exception as exc:
        log.warning("Failed to save debug files: %s", exc)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {"entries": []}


def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    log.info("History saved to %s", HISTORY_FILE)


def update_history(history, entry):
    current_month = entry["date"][:7]
    for i, e in enumerate(history["entries"]):
        if e["date"][:7] == current_month:
            history["entries"][i] = entry
            log.info("Updated existing entry for %s", current_month)
            return history
    history["entries"].append(entry)
    log.info("Added new entry for %s", current_month)
    return history


# ---------------------------------------------------------------------------
# Calculations
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

    all_values = [e["value"] for e in entries]
    if all_values:
        stats["all_time_high"] = max(all_values)
        stats["all_time_low"] = min(all_values)

    return stats


# ---------------------------------------------------------------------------
# Home Assistant push (Supervisor API)
# ---------------------------------------------------------------------------

def push_to_homeassistant(entry, stats):
    """Push sensor state to HA via Supervisor internal API."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        log.warning("SUPERVISOR_TOKEN not set — not running as HA add-on?")
        return False

    url = "http://supervisor/core/api/states/sensor.funda_house_value"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    attrs = {
        "unit_of_measurement": "€",
        "friendly_name": "Funda Woningwaarde",
        "icon": "mdi:home-analytics",
        "state_class": "measurement",
        "address": entry.get("address") or "Onbekend",
        "last_scraped": entry["scraped_at"],
    }
    attrs.update({k: v for k, v in stats.items() if v is not None})

    payload = {"state": entry["value"], "attributes": attrs}

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        log.info("Pushed to HA: sensor.funda_house_value = €%s", f"{entry['value']:,}")
        return True
    except requests.RequestException as exc:
        log.error("Failed to push to Home Assistant: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run():
    """Single scrape run — called by run.sh on schedule."""
    options = load_options()

    email = options.get("funda_email", "")
    password = options.get("funda_password", "")

    if not email or not password:
        log.error("Funda credentials not configured. Set them in the add-on options.")
        return False

    entry = scrape_funda(email, password)
    if entry is None:
        return False

    history = load_history()
    history = update_history(history, entry)
    if entry.get("address"):
        history["address"] = entry["address"]
    save_history(history)

    stats = calculate_stats(history, entry["value"])

    log.info(
        "🏠 Funda Woningwaarde: €%s | Maand: %s | Jaar: %s | Datapunten: %d",
        f"{entry['value']:,}",
        f"€{stats['monthly_change']:+,} ({stats['monthly_change_pct']:+.2f}%)"
        if stats["monthly_change"] is not None else "n/a",
        f"€{stats['yearly_change']:+,} ({stats['yearly_change_pct']:+.2f}%)"
        if stats["yearly_change"] is not None else "n/a",
        stats["total_entries"],
    )

    push_to_homeassistant(entry, stats)
    return True


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
