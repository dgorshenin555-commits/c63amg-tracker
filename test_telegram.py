import unittest
from notify_telegram import build_message

class TelegramSettlementTests(unittest.TestCase):
    def test_official_win_without_new_fills_still_notifies(self):
        event={"result":"WIN","market":"Example market","outcome":"YES",
               "cost":10.0,"payout":20.0,"pnl":10.0}
        msg=build_message([], "copied", [event])
        self.assertIsNotNone(msg)
        self.assertIn("ПОБЕДА", msg)
        self.assertIn("+$10.00", msg)
    def test_loss_message(self):
        event={"result":"LOSS","market":"Example market","outcome":"YES",
               "cost":10.0,"payout":0.0,"pnl":-10.0}
        msg=build_message([], "all", [event])
        self.assertIn("ПОРАЖЕНИЕ",msg)
        self.assertIn("-$10.00",msg)
    def test_no_events_no_message(self):
        self.assertIsNone(build_message([], "all", []))
    def test_mode_filter_does_not_suppress_settlement(self):
        event={"result":"SPLIT","market":"Example market","outcome":"YES",
               "cost":10,"payout":10,"pnl":0}
        obs={"decision":"SKIPPED","side":"BUY","market":"Example market",
             "outcome":"YES","price":0.5,"reason":"risk_limit"}
        msg=build_message([obs],"copied",[event])
        self.assertIn("50/50",msg)
        self.assertNotIn("Пропущено:",msg)
if __name__=="__main__":
    unittest.main()
