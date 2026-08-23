from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SingleServerArchitectureTests(unittest.TestCase):
    def test_legacy_home_bridge_removed(self):
        self.assertFalse((ROOT / "scripts/homepage/home_bridge.py").exists())

    def test_central_server_is_single_process(self):
        text = (ROOT / "scripts/community/community_server.py").read_text(encoding="utf-8")
        self.assertIn('default=8770', text)
        self.assertIn('BrowserPipeline(', text)
        self.assertNotIn('8765', text)
        self.assertNotIn('subprocess.Popen', text)
        self.assertNotIn('socket.create_connection', text)
        self.assertNotIn('urllib.request', text)

    def test_browser_pipeline_opens_no_http_server(self):
        text = (ROOT / "scripts/community/browser_pipeline.py").read_text(encoding="utf-8")
        self.assertNotIn('ThreadingHTTPServer', text)
        self.assertNotIn('BaseHTTPRequestHandler', text)

    def test_extension_uses_only_central_local_port(self):
        for relative in [
            "browser_extension/youtube_home_collector/background.js",
            "browser_extension/youtube_home_collector/popup.js",
            "browser_extension/youtube_home_collector/manifest.json",
        ]:
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn('8770', text, relative)
            self.assertNotIn('8765', text, relative)


if __name__ == "__main__":
    unittest.main()
