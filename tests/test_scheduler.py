import json
import random
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import scheduler


class SchedulerTests(unittest.TestCase):
    def test_distribution_stays_in_daytime_window(self):
        target_date = datetime(2026, 9, 11).date()
        samples = [
            scheduler.sample_window_time(target_date, rng=random.Random(seed))
            for seed in range(1_000)
        ]
        hours = [
            value.hour + value.minute / 60 + value.second / 3_600
            for value in samples
        ]

        self.assertTrue(all(9 <= hour <= 21 for hour in hours))
        self.assertGreater(sum(hours) / len(hours), 14.7)
        self.assertLess(sum(hours) / len(hours), 15.3)

    def test_monthly_target_is_day_after_publication(self):
        target = scheduler.create_monthly_target(
            "2027-02",
            publication_day=28,
            now=datetime(2027, 2, 1),
            rng=random.Random(42),
        )

        self.assertEqual(target.date().isoformat(), "2027-03-01")
        self.assertTrue(scheduler.is_in_window(target))

    def test_quick_graceful_restart_retries_immediately(self):
        now = datetime(2026, 8, 17, 22, 30)
        state = {
            "scheduled_period": "2026-08",
            "scheduled_at": "2026-08-17T15:00:00",
            "retry_at": "2026-08-18T09:30:00",
            "consecutive_failures": 1,
            "graceful_shutdown_at": (
                now - timedelta(seconds=30)
            ).isoformat(timespec="seconds"),
        }

        with patch.object(scheduler, "save_state"):
            self.assertTrue(scheduler.prepare_startup(state, now))
            target, period, reason = scheduler.next_run(state, now, 10)

        self.assertEqual(target, now)
        self.assertEqual(period, "2026-08")
        self.assertEqual(reason, "manual restart retry")

    def test_crash_does_not_accelerate_retry(self):
        now = datetime(2026, 8, 17, 22, 30)
        state = {
            "scheduled_period": "2026-08",
            "scheduled_at": "2026-08-17T15:00:00",
            "retry_at": "2026-08-18T09:30:00",
            "consecutive_failures": 1,
        }

        with patch.object(scheduler, "save_state"):
            self.assertFalse(scheduler.prepare_startup(state, now))
            target, _, reason = scheduler.next_run(state, now, 10)

        self.assertEqual(target, datetime(2026, 8, 18, 9, 30))
        self.assertEqual(reason, "retry")

    def test_state_write_is_atomic(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_file = Path(temporary_directory) / "scheduler_state.json"
            with patch.object(scheduler, "DATA_DIR", Path(temporary_directory)), patch.object(
                scheduler, "STATE_FILE", state_file
            ):
                scheduler.save_state({"scheduled_period": "2026-09"})

            self.assertEqual(
                scheduler.load_json(state_file, {}),
                {"scheduled_period": "2026-09"},
            )
            self.assertFalse(state_file.with_suffix(".json.tmp").exists())

    def test_changed_publication_day_replans_monthly_target(self):
        now = datetime(2026, 8, 20, 12, 0)
        state = {
            "last_success_period": "2026-08",
            "publication_day": 10,
            "scheduled_period": "2026-09",
            "scheduled_at": "2026-09-11T15:00:00",
        }

        with patch.object(scheduler, "save_state"):
            target, period, reason = scheduler.next_run(
                state,
                now,
                publication_day=15,
                rng=random.Random(42),
            )

        self.assertEqual(state["publication_day"], 15)
        self.assertEqual(period, "2026-09")
        self.assertEqual(target.date().isoformat(), "2026-09-16")
        self.assertEqual(reason, "monthly")

    def test_deprecated_schedule_hour_is_ignored_with_warning(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            options_file = Path(temporary_directory) / "options.json"
            options_file.write_text(json.dumps({
                "schedule_day": 10,
                "schedule_hour": 14,
            }))

            with patch.object(scheduler, "OPTIONS_FILE", options_file), self.assertLogs(
                scheduler.log, level="WARNING"
            ) as captured:
                publication_day = scheduler.load_options()

        self.assertEqual(publication_day, 10)
        self.assertIn("schedule_hour is deprecated", captured.output[0])

    def test_v101_history_infers_last_successful_period(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            history_file = Path(temporary_directory) / "history.json"
            history_file.write_text(json.dumps({
                "entries": [
                    {
                        "date": "2026-07-10",
                        "value": 592_000,
                        "scraped_at": "2026-07-10T10:00:00",
                    }
                ]
            }))

            with patch.object(scheduler, "HISTORY_FILE", history_file), patch.object(
                scheduler, "STATE_FILE", Path(temporary_directory) / "missing.json"
            ):
                state = scheduler.load_state()

        self.assertEqual(state["last_success_period"], "2026-07")

    def test_stale_v101_history_schedules_current_period_catch_up(self):
        now = datetime(2026, 8, 17, 16, 0)
        state = {"last_success_period": "2026-07"}

        with patch.object(scheduler, "save_state"):
            target, period, reason = scheduler.next_run(
                state,
                now,
                publication_day=10,
                rng=random.Random(42),
            )

        self.assertEqual(period, "2026-08")
        self.assertEqual(target.date(), now.date())
        self.assertGreaterEqual(target, now + scheduler.MINIMUM_LEAD_TIME)
        self.assertTrue(scheduler.is_in_window(target))
        self.assertEqual(reason, "monthly")


if __name__ == "__main__":
    unittest.main()
