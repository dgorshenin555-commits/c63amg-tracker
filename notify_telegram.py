"""Send paper-trade notifications via Telegram; never places real orders."""
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

ALERTS_PATH = pathlib.Path(".alerts.json")
SITE_URL = "https://dgorshenin555-commits.github.io/c63amg-tracker/"

def utc_time(epoch):
    try:
        return datetime.fromtimestamp(int(epoch), timezone.utc).strftime("%H:%M UTC")
    except (TypeError, ValueError, OverflowError):
        return "—"

def format_line(event):
    is_copy = event.get("decision") == "COPIED"
    action = "BUY" if event.get("side") == "BUY" else "SELL"
    title = " ".join(str(event.get("market", "")).split())[:90] or "Unnamed market"
    choice = " ".join(str(event.get("outcome", "")).split())[:35]
    signal_price = float(event.get("price", 0) or 0)
    if is_copy:
        qty = float(event.get("qty", 0) or 0)
        amount = float(event.get("spent", event.get("proceeds", 0)) or 0)
        fill_price = float(event.get("sim_price", 0) or 0)
        return (f"✅ {action} · {title}\n"
                f"   Outcome: {choice} | C63AMG: {signal_price:.3f} | paper: {fill_price:.3f}\n"
                f"   {qty:.2f} shares · ${amount:.2f} · {utc_time(event.get('ts'))}")
    reason = str(event.get("reason", "unknown"))[:60]
    return (f"⏭ {action} · {title}\n"
            f"   Outcome: {choice} | Source: {signal_price:.3f} · skipped: {reason}")

def build_message(events, mode):
    selected = [e for e in events if mode == "all" or e.get("decision") == "COPIED"]
    if not selected:
        return None
    copied = sum(e.get("decision") == "COPIED" for e in selected)
    shown = selected[:12]
    lines = [f"📊 C63AMG Paper Tracker · {copied} virtual copy / {len(selected)} new signals",
             "Simulation only — no real orders.", ""]
    lines.extend(format_line(e) for e in shown)
    if len(selected) > len(shown):
        lines.append(f"… and {len(selected)-len(shown)} more signals in the dashboard")
    lines.append(SITE_URL)
    return "\n".join(lines)[:4000]

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if "--discover" in sys.argv:
        if not token:
            print("Add TELEGRAM_BOT_TOKEN as a GitHub Actions secret first.")
            return 1
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/getUpdates",
                                     headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.load(response)
            updates = data.get("result", [])
            chats = []
            for update in updates:
                msg = update.get("message") or {}
                if msg.get("chat", {}).get("type") == "private" and str(msg.get("text", "")).strip().startswith("/start"):
                    chats.append(str(msg["chat"]["id"]))
            if not chats:
                print("No /start messages found. Open your bot in Telegram, tap Start, then try again.")
                return 1
            print("Found chat IDs for private /start messages: " + ", ".join(dict.fromkeys(chats[-10:])))
            print("Set your chosen ID as GitHub Actions secret TELEGRAM_CHAT_ID.")
            return 0
        except urllib.error.HTTPError as exc:
            print(f"Telegram discovery error: HTTP {exc.code}.")
            return 1
    if not token or not chat_id:
        print("Telegram is not configured: add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in GitHub Actions secrets.")
        return 0
    if "--test" in sys.argv:
        msg = f"✅ C63AMG Paper Tracker Telegram is connected. Virtual trades only.\n{SITE_URL}"
    else:
        if not ALERTS_PATH.exists():
            print("No alerts file; nothing to send.")
            return 0
        data = json.loads(ALERTS_PATH.read_text(encoding="utf-8"))
        mode = os.environ.get("TELEGRAM_NOTIFY_MODE", "copied").lower().strip()
        if mode not in ("copied", "all"):
            mode = "copied"
        msg = build_message(data.get("events", []), mode)
        if not msg:
            print("No new qualifying signals for Telegram notification.")
            return 0
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": msg, "disable_web_page_preview": True}).encode()
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            status = response.status
            result = json.load(response)
        if status == 200 and result.get("ok") is True:
            print("Telegram message delivered successfully.")
            return 0
        print("Telegram returned an unsuccessful result.")
        return 1
    except urllib.error.HTTPError as exc:
        print(f"Telegram API error: HTTP {exc.code}; check bot activation and chat ID.")
        return 1
    except Exception as exc:
        print(f"Telegram notification failed: {type(exc).__name__}.")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
