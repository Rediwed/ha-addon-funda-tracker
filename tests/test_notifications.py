import os
import unittest
from unittest.mock import Mock, patch

import funda_scraper


class NotificationTests(unittest.TestCase):
    @patch.dict(os.environ, {"SUPERVISOR_TOKEN": "test-token"})
    @patch.object(funda_scraper.std_requests, "post")
    def test_failure_notification_uses_stable_id(self, post):
        post.return_value = Mock(raise_for_status=Mock())

        self.assertTrue(funda_scraper.notify_scrape_failure())

        _, kwargs = post.call_args
        self.assertEqual(
            kwargs["json"]["notification_id"],
            funda_scraper.FAILURE_NOTIFICATION_ID,
        )
        self.assertIn("ophalen mislukt", kwargs["json"]["title"])

    @patch.dict(os.environ, {"SUPERVISOR_TOKEN": "test-token"})
    @patch.object(funda_scraper.std_requests, "post")
    def test_success_dismisses_same_notification(self, post):
        post.return_value = Mock(raise_for_status=Mock())

        self.assertTrue(funda_scraper.dismiss_scrape_failure_notification())

        url, = post.call_args.args
        self.assertTrue(url.endswith("/persistent_notification/dismiss"))
        self.assertEqual(
            post.call_args.kwargs["json"],
            {"notification_id": funda_scraper.FAILURE_NOTIFICATION_ID},
        )


if __name__ == "__main__":
    unittest.main()