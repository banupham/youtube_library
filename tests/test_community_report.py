import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "community" / "build_community_report.py"
spec = importlib.util.spec_from_file_location("community_report", MODULE_PATH)
community = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(community)


def profile(participant, key, interests, certainty=0.8, days=7, keywords=None, tags=None):
    return {
        "schema_version": "1.0.0",
        "participant_id": participant,
        "device_id": f"device-{participant}",
        "profile_id": f"profile-{key}",
        "profile_key": key,
        "updated_at": "2026-08-23T00:00:00Z",
        "certainty_score": certainty,
        "daily_observation_count": days,
        "interest_weights": [
            {
                "id": cid,
                "name_vi": cid,
                "predicted_weight": weight,
                "trend_state": trend,
            }
            for cid, weight, trend in interests
        ],
        "intent_weights": [{"id": "tutorial", "label": "Tutorial", "weight": 1.0}],
        "keyword_trends": keywords or [],
        "tag_trends": tags or [],
    }


class CommunityReportTests(unittest.TestCase):
    def test_participant_balancing_caps_many_profiles(self):
        profiles = [
            profile("A", "A1", [("gaming", 0.9, "stable")]),
            profile("A", "A2", [("gaming", 0.9, "stable")]),
            profile("A", "A3", [("gaming", 0.9, "stable")]),
            profile("B", "B1", [("science_technology", 0.9, "rising")]),
        ]
        weights = community.participant_balanced_weights(profiles)
        a_total = weights["A1"] + weights["A2"] + weights["A3"]
        b_total = weights["B1"]
        self.assertAlmostEqual(a_total, 0.5, places=6)
        self.assertAlmostEqual(b_total, 0.5, places=6)

    def test_report_distinguishes_profiles_and_participants(self):
        profiles = [
            profile("A", "A1", [("gaming", 0.8, "stable")]),
            profile("A", "A2", [("gaming", 0.7, "stable")]),
            profile(
                "B",
                "B1",
                [("science_technology", 0.6, "rising"), ("gaming", 0.2, "emerging")],
                keywords=[
                    {"value": "AI creator", "weight": 0.5, "trend_state": "rising"},
                    {"value": "creator workflow", "weight": 0.3, "trend_state": "emerging"},
                ],
                tags=[{"value": "ai video", "weight": 0.4, "trend_state": "rising"}],
            ),
        ]
        report = community.build_report(profiles)
        self.assertEqual(report["community"]["participant_count"], 2)
        self.assertEqual(report["community"]["profile_count"], 3)

        lanes = {row["category_id"]: row for row in report["creator_opportunities"]}
        self.assertIn("gaming", lanes)
        self.assertIn("science_technology", lanes)
        self.assertEqual(lanes["gaming"]["matched_profile_count"], 3)
        self.assertEqual(lanes["gaming"]["matched_participant_count"], 2)
        self.assertEqual(lanes["science_technology"]["matched_participant_count"], 1)

    def test_rising_terms_can_become_expansion_keys(self):
        profiles = [
            profile(
                "A",
                "A1",
                [("science_technology", 0.7, "rising")],
                keywords=[
                    {"value": "AI video", "weight": 0.6, "trend_state": "stable"},
                    {"value": "agent workflow", "weight": 0.4, "trend_state": "rising"},
                ],
            ),
            profile(
                "B",
                "B1",
                [("science_technology", 0.5, "emerging")],
                keywords=[
                    {"value": "AI video", "weight": 0.5, "trend_state": "stable"},
                    {"value": "agent workflow", "weight": 0.3, "trend_state": "emerging"},
                ],
            ),
        ]
        report = community.build_report(profiles)
        lane = next(row for row in report["creator_opportunities"] if row["category_id"] == "science_technology")
        values = {row["value"] for row in lane["expansion_keywords"]}
        self.assertIn("agent workflow", values)


if __name__ == "__main__":
    unittest.main()
