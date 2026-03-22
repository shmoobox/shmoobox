#!/usr/bin/env bash
# reset_factory.sh
# Reset a remote Shmoobox to "first boot" state.

set -euo pipefail

TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
    echo "Usage: $0 user@host"
    exit 1
fi

echo "Resetting Shmoobox on $TARGET ..."

ssh "$TARGET" 'bash -s' <<'EOF'
set -euo pipefail

SERVICE="shmoobox-web"
CONFIG_FILE="/etc/shmoobox/config.json"
HOTSPOT_CONN="shmoobox-ap"

echo "[1/7] Stopping service ..."
sudo systemctl stop "$SERVICE" || true

echo "[2/7] Reading saved SSID from config, if present ..."
SAVED_SSID=""
if [[ -f "$CONFIG_FILE" ]]; then
    SAVED_SSID="$(python3 - <<'PY'
import json
path = "/etc/shmoobox/config.json"
try:
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    net = cfg.get("network", {})
    ssid = net.get("last_wifi_ssid") or ""
    print(ssid)
except Exception:
    print("")
PY
)"
fi

echo "[3/7] Removing app config ..."
sudo rm -f "$CONFIG_FILE"

echo "[4/7] Removing hotspot profile ..."
sudo nmcli connection delete "$HOTSPOT_CONN" >/dev/null 2>&1 || true

if [[ -n "$SAVED_SSID" ]]; then
    echo "[5/7] Removing saved client Wi-Fi profile: $SAVED_SSID"
    sudo nmcli connection delete "$SAVED_SSID" >/dev/null 2>&1 || true
else
    echo "[5/7] No saved SSID found in config."
fi

echo "[6/7] Restarting NetworkManager ..."
sudo systemctl restart NetworkManager

echo "[7/7] Starting service ..."
sudo systemctl start "$SERVICE"

echo
echo "Factory reset complete."
echo "Check status with:"
echo "  sudo systemctl status $SERVICE"
EOF

echo "Done."
echo "Check status with:"
echo "  ssh $TARGET sudo systemctl status shmoobox-web"
