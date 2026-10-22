# C63AMG on an existing Vultr VPS

This runs the **existing simulated account**, NOT a real-money trader. The existing GitHub Pages site can stay online temporarily. No wallet private key or Polymarket API trading credentials are required.

## Ubuntu 22.04 / 24.04

Do **not** run these commands on your Amnezia/VPN server. Choose the **unused** VPS.

1. Open Mac Terminal, connect with `ssh root@YOUR_VPS_IP` (or the configured non-root SSH username).
2. Verify Linux: `cat /etc/os-release`. The automated installer supports Ubuntu 22.04 / 24.04.
3. On the VPS (if using a sudo-enabled user, prefix system commands with sudo):
   ```bash
   sudo apt-get update
   sudo apt-get install -y git
   sudo git clone https://github.com/dgorshenin555-commits/c63amg-tracker.git /opt/c63amg-tracker
   cd /opt/c63amg-tracker
   sudo bash server/install-ubuntu.sh
   ```
4. Insert your existing Telegram bot token and numeric chat ID in **`sudo nano /etc/c63amg.env`**. Do not put them in a chat, commit, screenshot or paste them into another site. The installer does not copy GitHub Secrets; add them again locally. Keep `POLL_SECONDS=10` for initial testing.
5. Start and verify:
   ```bash
   sudo systemctl enable --now c63amg
   sudo systemctl status c63amg --no-pager
   sudo journalctl -u c63amg -n 35 --no-pager
   curl -fsS http://127.0.0.1:8765/state.json | python3 -m json.tool | head -n 20
   ```
   The `last_success` and `updated` metrics should advance, and `Copied` / `Skipped` should be visible in the logs.

## Private access to dashboard (first stage)

The web server binds **only 127.0.0.1:8765**, so it cannot be reached from the public internet (safer by default). On your Mac, in a *new local* terminal:

```bash
ssh -N -L 8765:127.0.0.1:8765 root@YOUR_VPS_IP
```

Then open **http://127.0.0.1:8765/dashboard/** on your Mac. Keep the SSH tunnel terminal open. This connects the browser to the VPS dashboard with live `state.json` updates.

For an always-clickable HTTPS URL on Mac and iPhone, set up a **dedicated domain/subdomain** and Caddy or equivalent HTTPS reverse proxy with authentication, pointed at `127.0.0.1:8765`. Do not expose the raw HTTP port. Configure DNS first; certificates normally require ports 80/443 and a resolvable hostname. We can set this up after confirming the tracker.

## Operational notes

- `systemctl restart c63amg` restarts the poller (does not erase the account).
- `journalctl -u c63amg -f` streams logs.
- `sudo systemctl stop c63amg` pauses monitoring.
- `sudo systemctl status c63amg-web` checks web service.
- Edit `POLL_SECONDS` in `/etc/c63amg.env` (minimum 5 s) then `sudo systemctl restart c63amg`.
- HTTP Data API publication itself may be delayed, so a 10-second polling interval does **not** guarantee 10-second trade-to-alert latency.
- `/var/lib/c63amg/state.json` is the authoritative VPS paper-account state after cutover. GitHub's `state.json` may become stale unless a separate sync is configured.
- Do **not** enable the VPS poller and GitHub Actions poller simultaneously for long. After the first successful VPS checks, disable the scheduled GitHub Actions `tracker` workflow or remove the `schedule` event from `.github/workflows/paper-tracker.yml`, to prevent duplicate alerts and separate paper accounts. Keep GitHub Pages publishing as a separate static deployment if needed.
- The GitHub page stays on the slower historic snapshot until we add VPS-to-GitHub publishing or a VPS HTTPS website.
- The installer uses a restricted `c63amg` system user. Telegram Secrets are stored only in root-owned `/etc/c63amg.env` mode 600. The local dashboard listens on loopback only.

## Before switching over

Verify the new VPS starts from the existing `state.json` (same cash, copied/skipped counts and positions), that its `updated` time advances, and that one fresh Telegram notification arrives before disabling the original scheduler.
