import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "scripts" / "community" / "community_server.py"
SPEC = importlib.util.spec_from_file_location("community_server_test_module", SERVER_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def sample_payload():
    return {
        "schema_version": "1.0.0",
        "participant_id": "participant-test",
        "device_id": "android-test-device",
        "profile_slot": "android-main",
        "sent_at": "2026-08-23T16:00:00Z",
        "snapshot": {
            "schema_version": "1.0.0",
            "platform": "android",
            "source_package": "com.google.android.youtube",
            "captured_at": "2026-08-23T16:00:00Z",
            "extraction_mode": "android_accessibility_node_tree_read_only",
            "surface_guess": {"surface": "home", "confidence": 0.8, "evidence": []},
            "tree_signature": "abcdef1234567890",
            "node_count": 1,
            "nodes": [{"text": "Example video"}],
        },
    }


class AndroidIngestServerTests(unittest.TestCase):
    def test_valid_android_snapshot_envelope(self):
        self.assertEqual(MODULE.validate_android_ingest(sample_payload()), [])

    def test_rejects_non_youtube_package(self):
        payload = sample_payload()
        payload["snapshot"]["source_package"] = "com.example.other"
        errors = MODULE.validate_android_ingest(payload)
        self.assertTrue(any("source_package" in error for error in errors))

    def test_rejects_node_count_mismatch(self):
        payload = sample_payload()
        payload["snapshot"]["node_count"] = 2
        errors = MODULE.validate_android_ingest(payload)
        self.assertTrue(any("does not match" in error for error in errors))

    def test_signature_dedup_helper(self):
        payload = sample_payload()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "2026-08-23.jsonl"
            path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            self.assertTrue(MODULE.file_contains_tree_signature(path, "abcdef1234567890"))
            self.assertFalse(MODULE.file_contains_tree_signature(path, "different-signature"))


if __name__ == "__main__":
    unittest.main()
