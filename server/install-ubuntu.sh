#!/usr/bin/env bash
# Installer for a dedicated Ubuntu 22.04/24.04 Vultr instance.
# Safe to re-run: does not overwrite existing virtual account or Telegram secrets.
set -euo pipefail
if [[ "$EUID" -ne 0 ]]; then echo "Run as root: sudo bash server/install-ubuntu.sh" >&2; exit 1; fi
if [[ ! -f /etc/os-release ]]; then echo "Unknown OS"; exit 1; fi
source /etc/os-release
if [[ "${ID:-}" != "ubuntu" ]]; then echo "Only Ubuntu is supported by this installer; detected: ${ID:-unknown}"; exit 1; fi
if [[ "${VERSION_ID:-}" != "22.04" && "${VERSION_ID:-}" != "24.04" ]]; then echo "Tested for Ubuntu 22.04/24.04 only"; exit 1; fi
if [[ ! -f ./monitor.py || ! -f ./valuation.py ]]; then echo "Run this command from the GitHub repo root"; exit 1; fi
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 git ca-certificates
if ! id -u c63amg >/dev/null 2>&1; then useradd --system --home-dir /var/lib/c63amg --shell /usr/sbin/nologin c63amg; fi
install -d -m 750 -o c63amg -g c63amg /var/lib/c63amg
install -d -m 750 -o c63amg -g c63amg /var/lib/c63amg/site
if [[ ! -s /var/lib/c63amg/state.json ]]; then
  if [[ ! -s state.json ]]; then echo "Missing GitHub portfolio snapshot state.json"; exit 1; fi
  install -m 600 -o c63amg -g c63amg state.json /var/lib/c63amg/state.json
  echo "Imported existing GitHub paper account."
else
  echo "Existing VPS paper account preserved."
fi
cp -a site/. /var/lib/c63amg/site/
chown -R c63amg:c63amg /var/lib/c63amg
if [[ ! -e /etc/c63amg.env ]]; then
  cat > /etc/c63amg.env <<'EOF'
# Configure locally. Never post your Telegram token in chat or GitHub.
POLL_SECONDS=10
TRACKER_REPO=/opt/c63amg-tracker
TRACKER_DATA=/var/lib/c63amg
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TELEGRAM_NOTIFY_MODE=all
# Change to VPS HTTPS dashboard URL after domain setup:
TRACKER_SITE_URL=https://dgorshenin555-commits.github.io/c63amg-tracker/dashboard/
EOF
  chmod 600 /etc/c63amg.env
  echo "Created /etc/c63amg.env. Set Telegram secrets locally."
else
  echo "Existing /etc/c63amg.env preserved."
fi
install -m 644 server/c63amg.service /etc/systemd/system/c63amg.service
install -m 644 server/c63amg-web.service /etc/systemd/system/c63amg-web.service
systemctl daemon-reload
systemctl enable --now c63amg-web.service
echo
echo "Installed. No poller started yet. Next:"
echo "  1) sudo nano /etc/c63amg.env   # Set Telegram secrets locally"
echo "  2) sudo systemctl enable --now c63amg"
echo "  3) sudo journalctl -u c63amg -n 30 --no-pager"
echo "  4) curl http://127.0.0.1:8765/state.json"
echo "Open dashboard securely using an SSH tunnel until HTTPS is configured."
