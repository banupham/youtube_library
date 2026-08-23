import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHROME_BG = ROOT / "browser_extension" / "youtube_home_collector" / "background.js"
CHROME_PASSIVE = ROOT / "browser_extension" / "youtube_home_collector" / "passive_collector.js"
ANDROID = ROOT / "android_collector" / "app" / "src" / "main" / "java" / "com" / "youtube" / "library" / "collector"


class InteractionContractTests(unittest.TestCase):
    def test_chrome_score_contract(self):
        text = CHROME_BG.read_text(encoding="utf-8")
        expected = {
            "video_open": "0.25",
            "like": "1.0",
            "unlike": "-1.0",
            "dislike": "-1.0",
            "undislike": "1.0",
            "comment_submit": "1.0",
        }
        for event, value in expected.items():
            self.assertRegex(text, rf"\b{re.escape(event)}:\s*{re.escape(value)}\b")

    def test_android_reversible_toggle_contract(self):
        text = (ANDROID / "InteractionDetector.kt").read_text(encoding="utf-8")
        self.assertIn('eventType = if (selected) "dislike" else "undislike"', text)
        self.assertIn('score = if (selected) -1.0 else 1.0', text)
        self.assertIn('eventType = if (selected) "like" else "unlike"', text)
        self.assertIn('score = if (selected) 1.0 else -1.0', text)
        self.assertIn('eventType = "comment_submit"', text)
        self.assertIn('score = 1.0', text)

    def test_collectors_do_not_transmit_comment_content_fields(self):
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                CHROME_BG,
                CHROME_PASSIVE,
                ANDROID / "AndroidAutoSync.kt",
            ]
        )
        for forbidden in ("comment_text", "comment_body", "typed_text"):
            self.assertNotIn(forbidden, sources)


if __name__ == "__main__":
    unittest.main()
