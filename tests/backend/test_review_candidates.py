from django.test import SimpleTestCase

from scripts.build_asset_verification_manifest import build_candidates


class ReviewCandidateTests(SimpleTestCase):
    def test_attached_evidence_cannot_automatically_verify_an_asset(self):
        catalog = {
            "records": [
                {
                    "name": "Documented organization",
                    "location_precision": "exact",
                    "sources": [{"title": "Official drone research", "url": "https://example.org"}],
                }
            ]
        }
        candidates = build_candidates(catalog, "2026-09-04")
        self.assertEqual(candidates["reviewed_assets"], {})
        self.assertEqual(candidates["candidates"][0]["outcome"], "pending-editorial-review")
        self.assertEqual(candidates["record_count"], 1)
