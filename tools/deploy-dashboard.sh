#!/usr/bin/env bash
# Replace only the dashboard UI. Does not restart services or replace account data.
set -euo pipefail
bundle=$(mktemp -d)
trap 'rm -rf -- "$bundle"' EXIT
repo=${C63AMG_REPO:-/opt/c63amg-tracker}
release=47c0294cb7ee
git -C "$repo" rev-parse --verify "$release^{commit}" >/dev/null
mkdir -p "$bundle/site/dashboard"
for name in index.html dashboard/index.html dashboard.css dashboard.js; do
  git -C "$repo" show "$release:site/$name" > "$bundle/site/$name"
done
cat > "$bundle/SHA256SUMS" <<'CHECKSUMS'
c20229680dba93d7edf828406a3355ce81c0b51079d8c9dc43b0edbc206fcc0d  site/index.html
1f1a6941ff2451af356b38910455b9cf1a1eb8d832f796f535e8f73df860cf51  site/dashboard/index.html
a2375821dc653572e93611c761ccbf4b5bb5f480a82092ce8f578e7a020df051  site/dashboard.css
3ee73488008f8370baeff147a008b03e22ba8432e82efaca6a700f26960c3baf  site/dashboard.js
CHECKSUMS
web_root=${C63AMG_WEB_ROOT:-/var/lib/c63amg/site}
backup_root=${C63AMG_BACKUP_ROOT:-/var/lib/c63amg/dashboard-backups}
files=(index.html dashboard/index.html dashboard.css dashboard.js)
cd "$bundle"
sha256sum --check SHA256SUMS
if [[ ! -d "$web_root/dashboard" || ! -s "$web_root/state.json" ]]; then
  echo 'Existing dashboard directory and state.json are required.' >&2
  exit 1
fi
for name in "${files[@]}"; do
  if [[ -L "$web_root/$name" ]]; then
    echo "Refusing to replace a symlink: $name" >&2
    exit 1
  fi
done
backup="$backup_root/$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$backup/site"
state_hash=$(sha256sum "$web_root/state.json" | cut -d ' ' -f1)
for name in "${files[@]}"; do
  if [[ -e "$web_root/$name" ]]; then
    mkdir -p "$backup/site/$(dirname "$name")"
    cp -p -- "$web_root/$name" "$backup/site/$name"
    printf '%s\n' "$name" >> "$backup/existing-files"
  else
    printf '%s\n' "$name" >> "$backup/new-files"
  fi
done
rollback() {
  trap - ERR
  if [[ -e "$backup/existing-files" ]]; then
    while IFS= read -r name; do
      cp -p -- "$backup/site/$name" "$web_root/$name"
    done < "$backup/existing-files"
  fi
  if [[ -e "$backup/new-files" ]]; then
    while IFS= read -r name; do rm -f -- "$web_root/$name"; done < "$backup/new-files"
  fi
  echo "UI installation failed; previous UI restored from $backup" >&2
}
trap rollback ERR
for name in "${files[@]}"; do
  temporary=$(mktemp "$web_root/$(dirname "$name")/.dashboard-update.XXXXXX")
  install -m 644 "$bundle/site/$name" "$temporary"
  # Retain the web directory owner so the existing service can still manage files.
  chown --reference="$web_root" "$temporary"
  mv -f -- "$temporary" "$web_root/$name"
done
for name in "${files[@]}"; do cmp -- "$bundle/site/$name" "$web_root/$name"; done
if [[ "${C63AMG_VERIFY_HTTP:-1}" == 1 ]]; then
  expected=$(sha256sum "$bundle/site/dashboard/index.html" | cut -d ' ' -f1)
  observed=$(curl --fail --silent --show-error --max-time 15 http://127.0.0.1:8765/dashboard/ | sha256sum | cut -d ' ' -f1)
  [[ "$expected" == "$observed" ]]
fi
after_hash=$(sha256sum "$web_root/state.json" | cut -d ' ' -f1)
trap - ERR
echo "Installed dashboard UI. Backup: $backup"
if [[ "$state_hash" == "$after_hash" ]]; then
  echo 'state.json unchanged.'
else
  echo 'state.json changed during installation, potentially by the running poller; this installer never writes it.'
fi
echo 'No services, tunnels, Telegram settings or backend files were changed.'

echo "Dashboard URL: https://alot-permits-tracked-taxi.trycloudflare.com/dashboard/"
