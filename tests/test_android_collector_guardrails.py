import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "android_collector" / "app" / "src" / "main"
KOTLIN = ANDROID / "java" / "com" / "youtube" / "library" / "collector"


class AndroidCollectorGuardrailTests(unittest.TestCase):
    def test_snapshot_schema_is_valid_json(self):
        path = ROOT / "schemas" / "android_accessibility_snapshot.v1.schema.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["properties"]["source_package"]["const"], "com.google.android.youtube")
        self.assertEqual(payload["properties"]["extraction_mode"]["const"], "android_accessibility_node_tree_read_only")

    def test_android_ingest_schema_is_valid_json(self):
        path = ROOT / "schemas" / "android_snapshot_ingest.v1.schema.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        snapshot = payload["properties"]["snapshot"]["properties"]
        self.assertEqual(snapshot["source_package"]["const"], "com.google.android.youtube")
        self.assertEqual(snapshot["platform"]["const"], "android")

    def test_accessibility_service_is_youtube_only_and_listens_to_natural_clicks(self):
        xml = (ANDROID / "res" / "xml" / "accessibility_service_config.xml").read_text(encoding="utf-8")
        self.assertIn('android:packageNames="com.google.android.youtube"', xml)
        self.assertIn('android:canRetrieveWindowContent="true"', xml)
        self.assertIn('android:isAccessibilityTool="false"', xml)
        self.assertIn("typeViewClicked", xml)

    def test_service_has_no_action_or_input_injection_apis(self):
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                KOTLIN / "YouTubeAccessibilityService.kt",
                KOTLIN / "InteractionDetector.kt",
            ]
        )
        forbidden = [
            "performAction(",
            "dispatchGesture(",
            "GLOBAL_ACTION_",
            "ACTION_CLICK",
            "ACTION_SCROLL_",
            "ACTION_SET_TEXT",
        ]
        for token in forbidden:
            self.assertNotIn(token, sources, token)

    def test_manifest_network_is_limited_to_internet_without_overlay_or_package_scan(self):
        manifest = (ANDROID / "AndroidManifest.xml").read_text(encoding="utf-8")
        self.assertIn("android.permission.INTERNET", manifest)
        self.assertNotIn("android.permission.SYSTEM_ALERT_WINDOW", manifest)
        self.assertNotIn("QUERY_ALL_PACKAGES", manifest)

    def test_auto_sync_uses_snapshot_and_interaction_endpoints(self):
        kotlin = (KOTLIN / "AndroidAutoSync.kt").read_text(encoding="utf-8")
        self.assertIn('"/v1/android/snapshot"', kotlin)
        self.assertIn('"/v1/interaction"', kotlin)
        self.assertIn("Authorization", kotlin)
        self.assertIn("pending_snapshots.jsonl", kotlin)
        self.assertIn("pending_interactions.jsonl", kotlin)

    def test_comment_content_is_not_added_to_interaction_payload(self):
        kotlin = (KOTLIN / "AndroidAutoSync.kt").read_text(encoding="utf-8")
        self.assertNotIn("comment_text", kotlin)
        self.assertNotIn("comment_body", kotlin)


if __name__ == "__main__":
    unittest.main()
