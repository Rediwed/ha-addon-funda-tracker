#!/usr/bin/env python3
"""Persistent monthly scheduler for the Funda Tracker add-on."""

import json
import logging
import os
import random
import signal
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("FUNDA_DATA_DIR", "/data"))
OPTIONS_FILE = DATA_DIR / "options.json"
HISTORY_FILE = DATA_DIR / "history.json"
STATE_FILE = DATA_DIR / "scheduler_state.json"
SCRAPER_FILE = Path(os.environ.get("FUNDA_SCRAPER_FILE", "/app/funda_scraper.py"))

WINDOW_START_SECONDS = 9 * 60 * 60
WINDOW_END_SECONDS = 21 * 60 * 60
WINDOW_MEAN_SECONDS = 15 * 60 * 60
WINDOW_STDDEV_SECONDS = 3 * 60 * 60
RETRY_DELAY = timedelta(hours=6)
MINIMUM_LEAD_TIME = timedelta(minutes=5)
RANDOM = random.SystemRandom()


def load_json(file_path, default):
    try:
        with open(file_path) as file_handle:
            return json.load(file_handle)
    except FileNotFoundError:
        return default
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Could not read %s: %s", file_path, exc)
        return default


def save_state(state):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary_path = STATE_FILE.with_suffix(".json.tmp")
    with open(temporary_path, "w") as file_handle:
        json.dump(state, file_handle, indent=2, sort_keys=True)
    temporary_path.replace(STATE_FILE)


def load_options():
    options = load_json(OPTIONS_FILE, {})
    publication_day = int(options.get("schedule_day", 10))
    if not 1 <= publication_day <= 28:
        raise ValueError("schedule_day must be between 1 and 28")
    if "schedule_hour" in options:
        log.warning(
            "schedule_hour is deprecated and ignored; fetches are randomized "
            "between 09:00 and 21:00"
        )
    return publication_day


def period_from_date(value):
    return value.strftime("%Y-%m")


def period_date(period, day):
    year, month = (int(part) for part in period.split("-"))
    return date(year, month, day)


def shift_period(period, months):
    year, month = (int(part) for part in period.split("-"))
    month_index = year * 12 + month - 1 + months
    return f"{month_index // 12:04d}-{month_index % 12 + 1:02d}"


def latest_published_period(now, publication_day):
    current_period = period_from_date(now)
    if now.date() >= period_date(current_period, publication_day):
        return current_period
    return shift_period(current_period, -1)


def seconds_since_midnight(value):
    return value.hour * 3600 + value.minute * 60 + value.second


def is_in_window(value):
    seconds = seconds_since_midnight(value)
    return WINDOW_START_SECONDS <= seconds <= WINDOW_END_SECONDS


def sample_window_time(target_date, earliest=None, rng=RANDOM):
    """Sample a truncated normal time between 09:00 and 21:00."""
    lower_bound = WINDOW_START_SECONDS
    if earliest and earliest.date() == target_date:
        lower_bound = max(lower_bound, seconds_since_midnight(earliest))

    if lower_bound > WINDOW_END_SECONDS:
        return sample_window_time(target_date + timedelta(days=1), rng=rng)

    for _ in range(10_000):
        sampled = rng.normalvariate(WINDOW_MEAN_SECONDS, WINDOW_STDDEV_SECONDS)
        if lower_bound <= sampled <= WINDOW_END_SECONDS:
            return datetime.combine(target_date, datetime.min.time()) + timedelta(
                seconds=round(sampled)
            )

    midpoint = lower_bound + (WINDOW_END_SECONDS - lower_bound) / 2
    return datetime.combine(target_date, datetime.min.time()) + timedelta(
        seconds=round(midpoint)
    )


def next_allowed_time(now, earliest=None, rng=RANDOM):
    earliest = max(earliest or now, now + MINIMUM_LEAD_TIME)
    return sample_window_time(earliest.date(), earliest=earliest, rng=rng)


def infer_last_success_period():
    history = load_json(HISTORY_FILE, {})
    scrape_times = [
        entry.get("scraped_at")
        for entry in history.get("entries", [])
        if entry.get("scraped_at")
    ]
    if not scrape_times:
        return None
    try:
        return period_from_date(datetime.fromisoformat(max(scrape_times)))
    except ValueError:
        return None


def load_state():
    state = load_json(STATE_FILE, {})
    if "last_success_period" not in state:
        inferred_period = infer_last_success_period()
        if inferred_period:
            state["last_success_period"] = inferred_period
    return state


def choose_target_period(state, now, publication_day):
    published_period = latest_published_period(now, publication_day)
    if state.get("last_success_period", "") >= published_period:
        return shift_period(published_period, 1)
    return published_period


def create_monthly_target(period, publication_day, now, rng=RANDOM):
    target_date = period_date(period, publication_day) + timedelta(days=1)
    target = sample_window_time(target_date, rng=rng)
    if target <= now:
        return next_allowed_time(now, rng=rng)
    return target


def parse_target(value):
    try:
        return datetime.fromisoformat(value) if value else None
    except ValueError:
        return None


def next_run(state, now, publication_day, rng=RANDOM):
    previous_publication_day = state.get("publication_day")
    if previous_publication_day is None:
        state["publication_day"] = publication_day
        save_state(state)
    elif previous_publication_day != publication_day:
        state["publication_day"] = publication_day
        if not state.get("retry_at"):
            state.pop("scheduled_period", None)
            state.pop("scheduled_at", None)
        save_state(state)
        log.info(
            "Publication day changed from %s to %s; replanning monthly fetch",
            previous_publication_day,
            publication_day,
        )

    retry_target = parse_target(state.get("retry_at"))
    if retry_target:
        if retry_target <= now and not is_in_window(now):
            retry_target = next_allowed_time(now, rng=rng)
            state["retry_at"] = retry_target.isoformat(timespec="seconds")
            save_state(state)
        return retry_target, state["scheduled_period"], "retry"

    period = choose_target_period(state, now, publication_day)
    target = parse_target(state.get("scheduled_at"))
    if state.get("scheduled_period") != period or target is None:
        target = create_monthly_target(period, publication_day, now, rng=rng)
        state.update({
            "scheduled_period": period,
            "scheduled_at": target.isoformat(timespec="seconds"),
        })
        save_state(state)
    elif target <= now and not is_in_window(now):
        target = next_allowed_time(now, rng=rng)
        state["scheduled_at"] = target.isoformat(timespec="seconds")
        save_state(state)

    return target, period, "monthly"


def record_success(state, period, now):
    state["last_success_period"] = period
    state["last_success_at"] = now.isoformat(timespec="seconds")
    state["consecutive_failures"] = 0
    for key in (
        "scheduled_period",
        "scheduled_at",
        "retry_at",
        "last_failure_at",
        "version_scrape_pending",
        "version_scrape_at",
        "version_scrape_period",
    ):
        state.pop(key, None)
    save_state(state)


def record_failure(state, period, now, rng=RANDOM):
    retry_at = next_allowed_time(now, earliest=now + RETRY_DELAY, rng=rng)
    state.pop("version_scrape_pending", None)
    state.pop("version_scrape_at", None)
    state.pop("version_scrape_period", None)
    state["scheduled_period"] = period
    state["retry_at"] = retry_at.isoformat(timespec="seconds")
    state["last_failure_at"] = now.isoformat(timespec="seconds")
    state["consecutive_failures"] = state.get("consecutive_failures", 0) + 1
    save_state(state)
    return retry_at


def prepare_startup(state, now, publication_day):
    """Consume a graceful-shutdown marker and request one startup scrape."""
    shutdown_marker = state.pop("graceful_shutdown_at", None)
    graceful_shutdown = parse_target(shutdown_marker)
    first_start = not state.get("startup_initialized", False)
    state["startup_initialized"] = True

    for key in (
        "last_started_version",
        "version_scrape_pending",
        "version_scrape_at",
        "version_scrape_period",
        "manual_restart_retry",
    ):
        state.pop(key, None)

    if graceful_shutdown is None and not first_start:
        if shutdown_marker is not None:
            save_state(state)
        return None

    state.pop("retry_at", None)
    save_state(state)
    reason = "first start" if first_start and graceful_shutdown is None else "graceful restart"
    log.info("%s detected; running one immediate scrape", reason.capitalize())
    return reason, latest_published_period(now, publication_day)


def install_signal_handlers(state):
    def handle_shutdown(signum, _frame):
        state["graceful_shutdown_at"] = datetime.now().isoformat(timespec="seconds")
        save_state(state)
        log.info("Graceful shutdown recorded (signal %d)", signum)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)


def run_scraper():
    try:
        return subprocess.run([sys.executable, str(SCRAPER_FILE)], check=False).returncode == 0
    except OSError as exc:
        log.error("Could not start scraper: %s", exc)
        return False


def main():
    publication_day = load_options()
    state = load_state()
    startup_run = prepare_startup(state, datetime.now(), publication_day)
    install_signal_handlers(state)
    last_announced_target = None

    log.info("Funda publishes monthly data around day %d", publication_day)
    log.info("Fetch window: 09:00-21:00, normal distribution around 15:00")

    if startup_run:
        reason, period = startup_run
        log.info("Starting %s fetch for publication period %s", reason, period)
        if run_scraper():
            record_success(state, period, datetime.now())
            log.info("Fetch succeeded")
        else:
            retry_at = record_failure(state, period, datetime.now())
            log.error(
                "Fetch failed; next retry is scheduled for %s",
                retry_at.strftime("%d-%m-%Y %H:%M:%S"),
            )

    while True:
        now = datetime.now()
        target, period, reason = next_run(state, now, publication_day)
        target_key = (target, period, reason)
        if target_key != last_announced_target:
            log.info(
                "Next %s fetch for publication period %s: %s",
                reason,
                period,
                target.strftime("%d-%m-%Y %H:%M:%S"),
            )
            last_announced_target = target_key

        delay = (target - now).total_seconds()
        if delay > 0:
            time.sleep(min(delay, 300))
            continue

        now = datetime.now()
        if not is_in_window(now):
            state.pop("retry_at", None)
            state["scheduled_at"] = next_allowed_time(now).isoformat(timespec="seconds")
            save_state(state)
            last_announced_target = None
            continue

        log.info("Starting %s fetch for publication period %s", reason, period)
        if run_scraper():
            record_success(state, period, datetime.now())
            log.info("Fetch succeeded")
        else:
            retry_at = record_failure(state, period, datetime.now())
            log.error(
                "Fetch failed; next retry is scheduled for %s",
                retry_at.strftime("%d-%m-%Y %H:%M:%S"),
            )
        last_announced_target = None


if __name__ == "__main__":
    main()