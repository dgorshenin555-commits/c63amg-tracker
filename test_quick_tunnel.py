"""Offline tests of changing Cloudflare Quick Tunnel links; no network."""
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from server import quick_tunnel
import notify_telegram


class CloudflareTunnelTests(unittest.TestCase):
    def test_detects_random_public_url_in_cloudflared_log(self):
        line = "2026-10-23 INF | https://new-demo-tunnel.trycloudflare.com |"
        self.assertEqual(
            quick_tunnel.extract_dashboard_url(line),
            "https://new-demo-tunnel.trycloudflare.com/dashboard/",
        )

    def test_ignores_non_cloudflare_urls(self):
        self.assertIsNone(quick_tunnel.extract_dashboard_url("https://example.com"))
        self.assertIsNone(quick_tunnel.extract_dashboard_url("nothing yet"))

    def test_link_changed_is_saved_without_exposing_secrets(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root) / "link.txt"
            first = "https://alpha.trycloudflare.com/dashboard/"
            second = "https://beta.trycloudflare.com/dashboard/"
            self.assertTrue(quick_tunnel.publish_link(first, path))
            self.assertFalse(quick_tunnel.publish_link(first, path))
            self.assertTrue(quick_tunnel.publish_link(second, path))
            self.assertEqual(path.read_text().strip(), second)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_trade_notifications_reference_current_tunnel_url(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root) / "current-tunnel-url.txt"
            path.write_text("https://fresh.trycloudflare.com/dashboard/")
            with patch.object(notify_telegram, "TUNNEL_LINK_PATH", path):
                msg = notify_telegram.build_message(
                    [{"decision": "COPIED", "side": "BUY", "market": "Example", "price": 0.5}], "all"
                )
            self.assertIn("https://fresh.trycloudflare.com/dashboard/", msg)


if __name__ == "__main__":
    unittest.main()
