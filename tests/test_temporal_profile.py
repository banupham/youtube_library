import sys
import unittest
from datetime import date
from pathlib import Path

PROFILE_DIR = Path(__file__).resolve().parents[1] / "scripts" / "profile"
sys.path.insert(0, str(PROFILE_DIR))

from build_temporal_profile import rolling_vector, stable_profile_name, trend_state  # noqa: E402


def observation(day, weights, candidate="Music · Explorer"):
    return {
        "date": day,
        "candidate_profile_name": candidate,
        "interest_weights": {
            key: {"name_vi": key, "weight": value, "surfaces": {"home": value}}
            for key, value in weights.items()
        },
    }


class TemporalProfileTests(unittest.TestCase):
    def test_recent_days_receive_more_weight(self):
        rows = [
            observation("2026-08-20", {"music": 0.9, "gaming": 0.1}),
            observation("2026-08-23", {"music": 0.2, "gaming": 0.8}),
        ]
        vector = rolling_vector(
            rows,
            "interest_weights",
            date(2026, 8, 23),
            max_age_days=6,
            half_life_days=3.5,
        )
        self.assertGreater(vector["gaming"], vector["music"])

    def test_rising_interest_is_detected(self):
        rows = [
            observation("2026-08-20", {"ai": 0.10, "music": 0.90}),
            observation("2026-08-21", {"ai": 0.12, "music": 0.88}),
            observation("2026-08-22", {"ai": 0.13, "music": 0.87}),
            observation("2026-08-23", {"ai": 0.32, "music": 0.68}),
        ]
        state, confidence, _ = trend_state(
            "ai",
            0.32,
            0.12,
            0.17,
            rows,
            date(2026, 8, 23),
        )
        self.assertEqual(state, "rising")
        self.assertGreater(confidence, 0.4)

    def test_profile_name_requires_three_consecutive_days_to_change(self):
        previous = {"behavior_profile_name": "Music · Explorer"}
        two_days = [
            observation("2026-08-22", {"ai": 1.0}, "Technology · Tutorial Learner"),
            observation("2026-08-23", {"ai": 1.0}, "Technology · Tutorial Learner"),
        ]
        state = stable_profile_name("Technology · Tutorial Learner", two_days, previous)
        self.assertEqual(state["stable_name"], "Music · Explorer")

        three_days = [
            observation("2026-08-21", {"ai": 1.0}, "Technology · Tutorial Learner"),
            *two_days,
        ]
        state = stable_profile_name("Technology · Tutorial Learner", three_days, previous)
        self.assertEqual(state["stable_name"], "Technology · Tutorial Learner")


if __name__ == "__main__":
    unittest.main()
