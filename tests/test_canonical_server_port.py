import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "browser_extension" / "youtube_home_collector"


class CanonicalServerPortTests(unittest.TestCase):
    def test_extension_uses_central_8770(self):
        manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
        self.assertIn("http://127.0.0.1:8770/*", manifest["host_permissions"])
        self.assertNotIn("http://127.0.0.1:8765/*", manifest["host_permissions"])

        background = (EXT / "background.js").read_text(encoding="utf-8")
        self.assertIn("http://127.0.0.1:8770", background)
        self.assertNotIn("http://127.0.0.1:8765", background)

        popup = (EXT / "popup.html").read_text(encoding="utf-8")
        self.assertIn("127.0.0.1:8770", popup)

    def test_central_server_owns_external_8770(self):
        server = (ROOT / "scripts" / "community" / "community_server.py").read_text(encoding="utf-8")
        self.assertIn('parser.add_argument("--port", type=int, default=8770)', server)
        self.assertIn('default=8765', server)
        self.assertIn('"/collect"', server)
        self.assertIn('"/finalize"', server)

    def test_legacy_bridge_remains_internal_8765(self):
        bridge = (ROOT / "scripts" / "homepage" / "home_bridge.py").read_text(encoding="utf-8")
        self.assertIn('parser.add_argument("--port", type=int, default=8765)', bridge)


if __name__ == "__main__":
    unittest.main()
