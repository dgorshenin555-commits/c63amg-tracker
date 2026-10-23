"""Regression tests for frequent VPS polling without network access."""
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import monitor


class FastPollingTests(unittest.TestCase):
    def run_in_temp(self, deep=False):
        now = 1_800_000_000
        state = {
            "started": now - 1000,
            "end": now + 1000,
            "updated": now - 10,
            "last_deep_scan": 0 if deep else now - 5,
            "cash": 930.0,
            "realized": 0.0,
            "positions": {},
            "seen": [],
            "events": [],
            "copied": 7,
            "skipped": 22,
        }
        if not deep:
            state.update({
                "source_latest_known_ts": now - 5,
                "source_24h_sample_count": 6,
                "source_latest_markets": ["Previously seen market"],
            })
        with tempfile.TemporaryDirectory() as temp:
            current = os.getcwd()
            os.chdir(temp)
            try:
                path = pathlib.Path(temp) / "state.json"
                path.write_text(json.dumps(state))
                def value(s, fetch, book, timestamp):
                    s["equity"] = s["cash"]
                    return []
                diagnostic = {"data": [{"timestamp": now-3, "title": "Recent market"}]}
                with (
                    patch.object(monitor, "P", path),
                    patch.object(monitor, "NOW", now),
                    patch.dict(os.environ, {"C63AMG_FAST_POLL": "1"}),
                    patch.object(monitor, "trades", return_value=[]) as trades,
                    patch.object(monitor, "fetch", return_value=diagnostic) as fetch,
                    patch.object(monitor, "update_portfolio", side_effect=value),
                ):
                    monitor.run()
                result = json.loads(path.read_text())
                self.assertEqual(result["cash"], 930.0)
                self.assertEqual(result["copied"], 7)
                self.assertEqual(result["skipped"], 22)
                self.assertEqual(result["updated"], now)
                self.assertEqual(result["equity"], 930.0)
                self.assertEqual(result["feed_rows"], 0)
                self.assertTrue((pathlib.Path(temp) / "site/state.json").exists())
                if deep:
                    self.assertEqual(result["scan_mode"], "deep")
                    self.assertEqual(result["source_24h_sample_count"], 1)
                    self.assertEqual(result["source_latest_known_ts"], now-3)
                    self.assertEqual(fetch.call_count, 1)
                else:
                    self.assertEqual(result["scan_mode"], "fast")
                    self.assertEqual(result["source_24h_sample_count"], 6)
                    self.assertEqual(result["source_latest_known_ts"], now-5)
                    fetch.assert_not_called()
                self.assertEqual(trades.call_count, 1)
            finally:
                os.chdir(current)

    def test_fast_scan_without_local_sample_variable(self):
        self.run_in_temp(deep=False)

    def test_deep_scan_refreshes_cached_source_diagnostic(self):
        self.run_in_temp(deep=True)


if __name__ == "__main__":
    unittest.main()
