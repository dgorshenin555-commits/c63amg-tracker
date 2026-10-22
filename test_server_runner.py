"""Offline smoke tests for the Vultr runner (no network and no trading)."""
import unittest
from unittest.mock import patch
from server import runner

class RunnerTests(unittest.TestCase):
    def test_poll_then_notify(self):
        with patch.object(runner, "execute", side_effect=[0,0]) as execute:
            self.assertTrue(runner.run_once())
            self.assertEqual([call.args[0] for call in execute.call_args_list], ["monitor.py","notify_telegram.py"])

    def test_poll_error_does_not_send_notification(self):
        with patch.object(runner, "execute", side_effect=[1]) as execute:
            self.assertFalse(runner.run_once())
            self.assertEqual(execute.call_count,1)

    def test_telegram_failure_does_not_undo_saved_state(self):
        with patch.object(runner, "execute", side_effect=[0,1]) as execute:
            self.assertTrue(runner.run_once())
            self.assertEqual(execute.call_count,2)

if __name__ == "__main__":
    unittest.main()
