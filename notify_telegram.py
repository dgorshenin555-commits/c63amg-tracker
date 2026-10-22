"""Send paper-trade notifications via Telegram; never places real orders."""
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

ALERTS_PATH = pathlib.Path(".alerts.json")
SITE_URL = os.environ.get("TRACKER_SITE_URL", "https://dgorshenin555-commits.github.io/c63amg-tracker/dashboard/")

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
    meanings = {"late_or_invalid": "Сигнал старше 7 минут", "price_moved": "Цена изменилась",
                "risk_limit": "Достигнут лимит риска", "no_inventory": "Нет долей для продажи",
                "no_depth": "Нет доступных заявок", "price_filter": "Цена вне диапазона",
                "bad_signal": "Некорректные данные"}
    reason_text = meanings.get(reason, "Ошибка котировок" if reason.startswith("orderbook_error:") else reason)
    return (f"⏭ ОБНАРУЖЕНО, НЕ СКОПИРОВАНО · {action} · {title}\n"
            f"   Исход: {choice} | Цена C63AMG: {signal_price:.3f}\n"
            f"   Причина: {reason_text}")

def build_message(events, mode, settlements=None):
    settlements = settlements or []
    selected = [e for e in events if mode == "all" or e.get("decision") == "COPIED"]
    if not selected and not settlements:
        return None
    copied = sum(e.get("decision") == "COPIED" for e in selected)
    lines = ["📊 C63AMG · Виртуальный портфель",
             "Только виртуальный счёт, реальных покупок нет.", ""]
    if settlements:
        lines.append("🏁 ОФИЦИАЛЬНО РАССЧИТАННЫЕ СОБЫТИЯ:")
        for p in settlements[:8]:
            result = {"WIN": "✅ ПОБЕДА", "LOSS": "❌ ПОРАЖЕНИЕ", "SPLIT": "➗ 50/50"}.get(p.get("result"), "ИТОГ")
            pnl = float(p.get("pnl", 0))
            signed = ("+" if pnl >= 0 else "-") + "$" + f"{abs(pnl):.2f}"
            lines.extend([
                f"{result} · {p.get('market', '')}",
                f"   Исход: {p.get('outcome', '')} · Вложено ${float(p.get('cost',0)):.2f}",
                f"   Выплата: ${float(p.get('payout',0)):.2f} · Результат: {signed}",
            ])
        if len(settlements) > 8:
            lines.append(f"И ещё {len(settlements)-8} завершённых событий в панели.")
        lines.append("")
    if selected:
        lines.append(f"📌 Новые сигналы: {len(selected)} · виртуально скопировано: {copied} · пропущено: {len(selected)-copied}")
        lines.extend(format_line(e) for e in selected[:10])
        if len(selected) > 10:
            lines.append(f"И ещё {len(selected)-10} сигналов в панели.")
    lines.append(SITE_URL)
    return "\n".join(lines)[:4000]

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if "--discover" in sys.argv:
        if not token:
            print("Add TELEGRAM_BOT_TOKEN as a GitHub Actions secret first.")
            return 1
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/getUpdates",
            headers={"Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.load(response)
            updates = data.get("result", [])
            chats = []
            for update in updates:
                msg = update.get("message") or {}
                chat = msg.get("chat") or {}
                if chat.get("type") == "private" and chat.get("id") is not None:
                    chats.append(str(chat["id"]))
            chats = list(dict.fromkeys(chats[-5:]))
            if not chats:
                print("No private messages found. Message your own bot in Telegram, then run discover again.")
                return 1
            sent = 0
            for cid in chats:
                msg = ("✅ C63AMG Tracker: ваш Chat ID: " + cid +
                       "\nСоздайте GitHub Actions secret TELEGRAM_CHAT_ID с этим значением." +
                       "\nНе публикуйте ID в открытых журналах.")
                payload = json.dumps({"chat_id": cid, "text": msg}).encode()
                request = urllib.request.Request(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=15) as response:
                    result = json.load(response)
                    if result.get("ok"):
                        sent += 1
            print(f"Sent Chat ID privately in Telegram to {sent} recent private chat(s).")
            return 0 if sent else 1
        except urllib.error.HTTPError as exc:
            print(f"Telegram discovery error: HTTP {exc.code}.")
            return 1
        except Exception as exc:
            print(f"Telegram discovery error: {type(exc).__name__}.")
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
        msg = build_message(data.get("events", []), mode, data.get("settlements", []))
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
