import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "viewer" / "generate_viewers.py"
spec = importlib.util.spec_from_file_location("generate_viewers", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class ViewerGeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.categories = module.load_categories(ROOT / "taxonomy" / "homepage_categories.v1.json")
        cls.adjacency = module.load_adjacency(
            ROOT / "taxonomy" / "interest_relations.v1.json",
            set(cls.categories),
        )

    def assert_valid_vector(self, viewer):
        vector = viewer["interest_model"]["category_vector"]
        self.assertTrue(vector)
        self.assertAlmostEqual(sum(vector.values()), 1.0, places=5)
        self.assertTrue(viewer["interest_model"]["primary_interests"])
        self.assertEqual(module.validate_viewer(viewer), [])

    def test_pure_synthetic_is_structured(self):
        viewer = module.generate_pure_synthetic(
            categories=self.categories,
            adjacency=self.adjacency,
            master_seed=123,
            viewer_index=0,
            primary_override="gaming",
        )
        self.assert_valid_vector(viewer)
        primary = viewer["interest_model"]["primary_interests"][0]
        self.assertEqual(primary["id"], "gaming")
        self.assertEqual(primary["source"], "primary_seed")
        self.assertGreaterEqual(len(viewer["interest_model"]["secondary_interests"]), 1)
        self.assertEqual(viewer["seed_source"], "pure_synthetic")

    def test_same_seed_reproduces_model(self):
        first = module.generate_pure_synthetic(
            categories=self.categories,
            adjacency=self.adjacency,
            master_seed=999,
            viewer_index=7,
        )
        second = module.generate_pure_synthetic(
            categories=self.categories,
            adjacency=self.adjacency,
            master_seed=999,
            viewer_index=7,
        )
        self.assertEqual(first["viewer_id"], second["viewer_id"])
        self.assertEqual(first["random_seed"], second["random_seed"])
        self.assertEqual(first["interest_model"], second["interest_model"])
        self.assertEqual(first["preference_model"], second["preference_model"])

    def test_different_viewer_index_changes_viewer(self):
        first = module.generate_pure_synthetic(
            categories=self.categories,
            adjacency=self.adjacency,
            master_seed=42,
            viewer_index=0,
        )
        second = module.generate_pure_synthetic(
            categories=self.categories,
            adjacency=self.adjacency,
            master_seed=42,
            viewer_index=1,
        )
        self.assertNotEqual(first["viewer_id"], second["viewer_id"])
        self.assertNotEqual(first["random_seed"], second["random_seed"])

    def test_observed_profile_prior_preserves_main_direction(self):
        profile = {
            "analysis_version": "2.5.0",
            "certainty_score": 0.72,
            "behavior_profile_name": "Khoa học & Công nghệ · Tutorial Learner",
            "profile": {
                "profile_id": "browser-test-profile",
                "profile_short_id": "testprof",
            },
            "interest_weights": [
                {"id": "science_technology", "name_vi": "Khoa học & Công nghệ", "predicted_weight": 0.62},
                {"id": "education", "name_vi": "Giáo dục", "predicted_weight": 0.23},
                {"id": "business_finance", "name_vi": "Kinh doanh & Tài chính", "predicted_weight": 0.10},
                {"id": "gaming", "name_vi": "Trò chơi", "predicted_weight": 0.05},
            ],
            "intent_weights": [
                {"id": "tutorial", "weight": 0.70},
                {"id": "analysis", "weight": 0.30},
            ],
            "topic_map": [
                {"value": "Artificial intelligence", "score": 4.0},
                {"value": "Technology", "score": 2.0},
            ],
        }
        viewer = module.generate_observed_prior(
            profile=profile,
            categories=self.categories,
            adjacency=self.adjacency,
            master_seed=2026,
            viewer_index=0,
        )
        self.assert_valid_vector(viewer)
        self.assertEqual(viewer["seed_source"], "observed_profile_prior")
        self.assertEqual(
            viewer["interest_model"]["primary_interests"][0]["id"],
            "science_technology",
        )
        self.assertGreater(
            viewer["preference_model"]["intent_preferences"].get("tutorial", 0),
            viewer["preference_model"]["intent_preferences"].get("analysis", 0),
        )
        self.assertEqual(viewer["lineage"]["source_profile_id"], "browser-test-profile")
        self.assertTrue(viewer["interest_model"]["topic_vector"])

    def test_batch_count(self):
        viewers = module.build_batch(
            mode="pure_synthetic",
            count=25,
            master_seed=11,
            categories=self.categories,
            adjacency=self.adjacency,
            profile=None,
            primary=None,
        )
        self.assertEqual(len(viewers), 25)
        self.assertEqual(len({viewer["viewer_id"] for viewer in viewers}), 25)
        for viewer in viewers:
            self.assert_valid_vector(viewer)


if __name__ == "__main__":
    unittest.main()
