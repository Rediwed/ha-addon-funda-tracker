import unittest
from unittest.mock import Mock

import funda_scraper


class AuthenticationSecurityTests(unittest.TestCase):
    def test_rejects_non_funda_form_destination(self):
        session = Mock()

        response = funda_scraper._post_trusted_form(
            session,
            "https://login.funda.nl/account/login",
            "https://attacker.example/collect",
            {"UserName": "user@example.com", "Password": "secret"},
        )

        self.assertIsNone(response)
        session.post.assert_not_called()

    def test_rejects_redirect_that_preserves_post_body(self):
        session = Mock()
        session.post.return_value = Mock(
            status_code=307,
            headers={"Location": "/redirect"},
            url="https://login.funda.nl/account/login",
        )

        response = funda_scraper._post_trusted_form(
            session,
            "https://login.funda.nl/account/login",
            "/account/login",
            {"UserName": "user@example.com", "Password": "secret"},
        )

        self.assertIsNone(response)
        session.get.assert_not_called()

    def test_follows_trusted_redirect_as_get(self):
        session = Mock()
        session.post.return_value = Mock(
            status_code=302,
            headers={"Location": "https://www.funda.nl/mijn-huis/auth/callback"},
            url="https://login.funda.nl/account/login",
        )
        final_response = Mock(status_code=200, headers={}, url="https://www.funda.nl/mijn-huis/")
        session.get.return_value = final_response

        response = funda_scraper._post_trusted_form(
            session,
            "https://login.funda.nl/account/login",
            "/account/login",
            {"UserName": "user@example.com", "Password": "secret"},
        )

        self.assertIs(response, final_response)
        session.get.assert_called_once_with(
            "https://www.funda.nl/mijn-huis/auth/callback",
            allow_redirects=False,
        )


if __name__ == "__main__":
    unittest.main()