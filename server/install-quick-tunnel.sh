#!/usr/bin/env bash
# Install autostarting, accountless Cloudflare Quick Tunnel.
# Does not touch Amnezia, Docker, ports, Polymarket account or Telegram secrets.
set -euo pipefail
if [[ "${EUID}" -ne 0 ]]; then echo "Run as root" >&2; exit 1; fi
if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared missing; install the official Cloudflare package first." >&2
  exit 1
fi
if [[ ! -f server/c63amg-cloudflare.service || ! -f server/quick_tunnel.py ]]; then
  echo "Run from /opt/c63amg-tracker after git pull." >&2
  exit 1
fi
if ! curl -fsS -o /dev/null http://127.0.0.1:8765/dashboard/; then
  echo "C63AMG local dashboard not responding at 127.0.0.1:8765." >&2
  exit 1
fi
install -m 644 server/c63amg-cloudflare.service /etc/systemd/system/c63amg-cloudflare.service
systemctl daemon-reload
systemctl enable --now c63amg-cloudflare.service
echo "Cloudflare Quick Tunnel service enabled. It will start when the VPS boots."
echo "Current service:"
systemctl is-active c63amg-cloudflare.service
echo "Public link (if already assigned):"
if [[ -s /var/lib/c63amg/current-tunnel-url.txt ]]; then
  cat /var/lib/c63amg/current-tunnel-url.txt
else
  echo "Not assigned yet. See: journalctl -u c63amg-cloudflare -n 40 --no-pager"
fi
echo "A changed Quick Tunnel URL will be sent to the configured Telegram bot."
echo "Quick Tunnels have no uptime guarantee and change URL after service restarts."
