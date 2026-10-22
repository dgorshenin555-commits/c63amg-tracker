#!/usr/bin/env python3
"""Run C63AMG simulation locally on the VPS. No keys or live orders."""
from __future__ import annotations
import fcntl
import os
import pathlib
import subprocess
import sys
import time

REPO = pathlib.Path(os.environ.get("TRACKER_REPO", "/opt/c63amg-tracker")).resolve()
WORK = pathlib.Path(os.environ.get("TRACKER_DATA", "/var/lib/c63amg")).resolve()
INTERVAL = max(5, int(os.environ.get("POLL_SECONDS", "10")))
LOCK = WORK / ".poller.lock"

def execute(script: str) -> int:
    env = os.environ.copy()
    env["C63AMG_FAST_POLL"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, str(REPO / script)],
        cwd=str(WORK), env=env, check=False,
    )
    return result.returncode

def run_once() -> bool:
    start = time.monotonic()
    result = execute("monitor.py")
    if result != 0:
        print(f"Polling error, exit code {result}. Notifications were not attempted.", flush=True)
        return False
    alert_result = execute("notify_telegram.py")
    if alert_result != 0:
        print(f"Telegram notification error: exit code {alert_result}. State saved.", flush=True)
    print(f"VPS poll finished in {time.monotonic()-start:.2f}s", flush=True)
    return True

def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    with LOCK.open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("A second C63AMG poller is already running. Exiting.", flush=True)
            return 1
        failures = 0
        print(f"C63AMG VPS poller started. Interval={INTERVAL}s. Workdir={WORK}", flush=True)
        while True:
            started = time.monotonic()
            ok = run_once()
            failures = 0 if ok else min(failures + 1, 6)
            if "--once" in sys.argv:
                return 0 if ok else 1
            wait = max(0.5, INTERVAL - (time.monotonic() - started))
            if failures:
                wait = max(wait, min(120, 5 * (2 ** (failures - 1))))
            time.sleep(wait)

if __name__ == "__main__":
    raise SystemExit(main())
