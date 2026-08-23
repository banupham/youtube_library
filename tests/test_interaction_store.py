import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "community" / "interaction_store.py"
spec = importlib.util.spec_from_file_location("interaction_store", MODULE_PATH)
interaction = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(interaction)


def event(event_id, event_type, score, day="2026-08-24"):
    return {
        "schema_version": "1.0.0",
        "event_id": event_id,
        "participant_id": "participant-A",
        "device_id": "device-A",
        "profile_id": "browser-profile-A",
        "profile_slot": "browser-default",
        "platform": "browser",
        "captured_at": f"{day}T00:00:00+00:00",
        "event_type": event_type,
        "engagement_score": score,
        "score_model": "natural_interaction_v1",
        "source": "natural_user_action",
        "video_id": "abcdefghijk",
        "video_title": "Example",
        "channel": "Example Channel",
        "channel_subscription_state": "subscribed",
        "surface": "watch",
        "confidence": 1.0,
        "context": {"detection": "test"},
    }


class InteractionStoreTests(unittest.TestCase):
    def test_daily_score_and_dedupe(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = interaction.InteractionStore(Path(tmp))
            status, first = store.ingest(event("evt-00000001", "video_open", 0.25))
            self.assertEqual(status, 200)
            self.assertFalse(first["duplicate"])
            status, second = store.ingest(event("evt-00000002", "like", 1.0))
            self.assertEqual(status, 200)
            self.assertAlmostEqual(second["daily_score"], 1.25)
            status, duplicate = store.ingest(event("evt-00000002", "like", 1.0))
            self.assertTrue(duplicate["duplicate"])
            self.assertAlmostEqual(duplicate["daily_score"], 1.25)

    def test_comment_text_is_rejected(self):
        payload = event("evt-00000003", "comment_submit", 1.0)
        payload["comment_text"] = "do not store me"
        errors = interaction.validate_interaction(payload)
        self.assertTrue(any("forbidden" in row for row in errors))

    def test_profile_summary_contains_rolling_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = interaction.InteractionStore(Path(tmp))
            store.ingest(event("evt-00000004", "comment_submit", 1.0))
            summary = store.summary_for_profile("browser-profile-A")
            self.assertIsNotNone(summary)
            self.assertIn("rolling_7d", summary)
            self.assertIn("rolling_30d", summary)
            self.assertEqual(summary["rolling_7d"]["event_counts"]["comment_submit"], 1)


if __name__ == "__main__":
    unittest.main()
