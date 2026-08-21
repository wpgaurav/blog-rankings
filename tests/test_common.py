from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from common import canonical_url, ranked_entries, weighted_score  # noqa: E402


class CommonTests(unittest.TestCase):
    def test_weighted_score(self) -> None:
        scores = {
            "editorial_quality": 90,
            "trust": 80,
            "reach": 70,
            "freshness": 60,
            "ux": 50,
            "impact": 40,
        }
        self.assertEqual(73.0, weighted_score(scores))

    def test_canonical_url_removes_tracking_and_www(self) -> None:
        self.assertEqual(
            "https://example.com/blog/",
            canonical_url("https://www.example.com/blog?utm_source=test#top"),
        )

    def test_ranking_uses_editorial_quality_as_first_tiebreak(self) -> None:
        base = {
            "canonical_url": "https://example.com/",
            "scores": {
                "editorial_quality": 80,
                "trust": 80,
                "reach": 80,
                "freshness": 80,
                "ux": 80,
                "impact": 80,
            },
        }
        first = {**base, "id": "first", "name": "First"}
        second_scores = dict(base["scores"])
        second_scores["editorial_quality"] = 81
        second_scores["impact"] = 74
        second = {
            **base,
            "id": "second",
            "name": "Second",
            "canonical_url": "https://second.example/",
            "scores": second_scores,
        }
        ranked = ranked_entries([first, second])
        self.assertEqual("second", ranked[0]["id"])


if __name__ == "__main__":
    unittest.main()
