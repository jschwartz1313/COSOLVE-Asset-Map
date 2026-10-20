import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase

from scripts.audit_catalog_sources import classify_response, fetch


class SourceLoginRedirectTests(SimpleTestCase):
    def response(self, **overrides):
        return {
            "url": "https://example.org/public-evidence",
            "http_status": 200,
            "title": "",
            "text": "Public evidence",
            **overrides,
        }

    def test_captured_civicplus_sign_in_redirect_is_inconclusive(self):
        response = self.response(
            url="https://www.charlescityva.us/FormCenter/Main-County-Office-5/Contact-Us-44",
            final_url="https://cpauthentication.civicplus.com/Identity/Account/Login",
            title="Sign In - Authentication CivicPlus",
        )
        self.assertEqual(classify_response(response), "access_blocked_or_rate_limited")

    def test_terminal_login_segments_ignore_case_query_and_trailing_slash(self):
        for path in (
            "/Identity/Account/LOGIN/",
            "/Portal/SignIn?returnUrl=%2Fpublic-evidence",
            "/Accounts/Sign-In/#continue",
            "/accounts/login",
            "/login/",
            "/signin/",
            "/sign-in/",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    classify_response(self.response(final_url=f"https://example.org{path}")),
                    "access_blocked_or_rate_limited",
                )

    def test_login_words_inside_public_content_paths_remain_reachable(self):
        for path in (
            "/login-research",
            "/research/how-to-signin",
            "/login/research",
            "/guides/sign-in-instructions",
            "/ipeds/datacenter/loginRedirector2.aspx",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    classify_response(self.response(final_url=f"https://example.org{path}")),
                    "reachable",
                )

    def test_explicit_login_source_is_not_mistaken_for_new_redirect(self):
        for path in ("/login", "/Identity/Account/Login", "/PORTAL/SIGNIN"):
            with self.subTest(path=path):
                self.assertEqual(
                    classify_response(self.response(
                        url=f"https://example.org{path}",
                        final_url=f"https://example.org{path.lower()}/",
                    )),
                    "reachable",
                )

    def test_http_failure_classification_still_takes_precedence(self):
        for status, expected in ((404, "http_not_found"), (503, "server_error")):
            with self.subTest(status=status):
                self.assertEqual(
                    classify_response(self.response(
                        http_status=status,
                        final_url="https://example.org/Identity/Account/Login",
                    )),
                    expected,
                )

    def test_cached_observation_is_reclassified_without_fetch_or_rewriting_evidence(self):
        response = self.response(
            final_url="https://cpauthentication.civicplus.com/Identity/Account/Login",
            title="Sign In - Authentication CivicPlus",
            classification="reachable",
        )
        with TemporaryDirectory() as directory:
            cache = Path(directory)
            cache_path = cache / (hashlib.sha256(response["url"].encode()).hexdigest() + ".json")
            before = json.dumps(response).encode()
            cache_path.write_bytes(before)
            with patch("scripts.audit_catalog_sources.build_opener") as opener:
                result = fetch(response["url"], cache, refresh=False)
            opener.assert_not_called()
            self.assertEqual(result["classification"], "access_blocked_or_rate_limited")
            self.assertEqual(cache_path.read_bytes(), before)
