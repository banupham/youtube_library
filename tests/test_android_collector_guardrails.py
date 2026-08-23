import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "android_collector" / "app" / "src" / "main"


class AndroidCollectorGuardrailTests(unittest.TestCase):
    def test_snapshot_schema_is_valid_json(self):
        path = ROOT / "schemas" / "android_accessibility_snapshot.v1.schema.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["properties"]["source_package"]["const"], "com.google.android.youtube")
        self.assertEqual(payload["properties"]["extraction_mode"]["const"], "android_accessibility_node_tree_read_only")

    def test_accessibility_service_is_youtube_only(self):
        xml = (ANDROID / "res" / "xml" / "accessibility_service_config.xml").read_text(encoding="utf-8")
        self.assertIn('android:packageNames="com.google.android.youtube"', xml)
        self.assertIn('android:canRetrieveWindowContent="true"', xml)
        self.assertIn('android:isAccessibilityTool="false"', xml)

    def test_service_has_no_interaction_apis(self):
        kotlin = (ANDROID / "java" / "com" / "youtube" / "library" / "collector" / "YouTubeAccessibilityService.kt").read_text(encoding="utf-8")
        forbidden = [
            "performAction(",
            "dispatchGesture(",
            "GLOBAL_ACTION_",
            "ACTION_CLICK",
            "ACTION_SCROLL_",
            "ACTION_SET_TEXT",
        ]
        for token in forbidden:
            self.assertNotIn(token, kotlin, token)

    def test_manifest_does_not_request_network_or_overlay_permissions(self):
        manifest = (ANDROID / "AndroidManifest.xml").read_text(encoding="utf-8")
        self.assertNotIn("android.permission.INTERNET", manifest)
        self.assertNotIn("android.permission.SYSTEM_ALERT_WINDOW", manifest)
        self.assertNotIn("QUERY_ALL_PACKAGES", manifest)


if __name__ == "__main__":
    unittest.main()
