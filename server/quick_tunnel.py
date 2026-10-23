#!/usr/bin/env python3
"""Keep a Cloudflare Quick Tunnel available without an open SSH session.

Quick Tunnel addresses are not permanent: on each new address, save it for
the paper-trade notifier and send the operator a fresh Telegram link.
No wallet keys or trading calls are used here.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import urllib.request

WORK = pathlib.Path(os.environ.get("TRACKER_DATA", "/var/lib/c63amg"))
LINK_FILE = WORK / "current-tunnel-url.txt"
URL_PATTERN = re.compile(r"https://[a-z0-9]+(?:-[a-z0-9]+)*\.trycloudflare\.com\b", re.I)


def extract_dashboard_url(line: str) -> str | None:
    match = URL_PATTERN.search(line)
    return match.group(0).lower() + "/dashboard/" if match else None


def publish_link(url: str, link_file: pathlib.Path = LINK_FILE) -> bool:
    previous = link_file.read_text().strip() if link_file.is_file() else ""
    if previous == url:
        return False
    link_file.parent.mkdir(parents=True, exist_ok=True)
    handle, tmpname = tempfile.mkstemp(prefix=".tunnel-link-", dir=str(link_file.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as output:
            output.write(url + "\n")
        os.chmod(tmpname, 0o600)
        os.replace(tmpname, link_file)
    finally:
        if os.path.exists(tmpname):
            os.unlink(tmpname)
    return True


def send_link(url: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        print("Quick Tunnel ready; Telegram not configured.", flush=True)
        return
    message = (
        "🌐 C63AMG · Живая панель VPS\n"
        "Новая ссылка после запуска туннеля:\n"
        + url
        + "\n\nТолько виртуальные сделки. Ссылка открыта всем, кто её знает."
    )
    payload = json.dumps({
        "chat_id": chat, "text": message, "disable_web_page_preview": True
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.telegram.org/bot" + token + "/sendMessage",
        data=payload, headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.load(response)
        if data.get("ok"):
            print("Updated dashboard URL delivered to Telegram.", flush=True)
        else:
            print("Telegram did not confirm the dashboard URL notification.", flush=True)
    except Exception as exc:
        print("Dashboard URL Telegram notice failed: " + type(exc).__name__, flush=True)


def main() -> int:
    command = ["/usr/bin/cloudflared", "tunnel", "--url", "http://127.0.0.1:8765"]
    print("C63AMG Cloudflare Quick Tunnel starting (URL changes after restart).", flush=True)
    with subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, text=True, bufsize=1,
        env={key: value for key, value in os.environ.items()
             if key not in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")},
    ) as process:
        announced: set[str] = set()
        for line in process.stdout:
            print(line.rstrip(), flush=True)
            url = extract_dashboard_url(line)
            if url and url not in announced:
                announced.add(url)
                if publish_link(url):
                    print("Current public dashboard: " + url, flush=True)
                    send_link(url)
        return process.wait()


if __name__ == "__main__":
    sys.exit(main())
