#!/usr/bin/env bash
# install.sh
# Push code to appliance 

set -euo pipefail

TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
  echo "Usage: $0 <user@host-or-host>"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Repo root is $REPO_ROOT"

if [[ ! -d "$REPO_ROOT/app" ]]; then
  echo "Error: could not find repo root"
  exit 1
fi

echo "Deploying Shmoobox to $TARGET ..."

ssh "$TARGET" 'mkdir -p /tmp/shmoobox-deploy'
scp "$REPO_ROOT/app/app.py" "$TARGET:/tmp/shmoobox-deploy/app.py"
scp "$REPO_ROOT/deploy/shmoobox-web.service" "$TARGET:/tmp/shmoobox-deploy/shmoobox-web.service"
scp "$REPO_ROOT/config/config.example.json" "$TARGET:/tmp/shmoobox-deploy/config.example.json"

ssh "$TARGET" 'bash -s' <<'EOF'
set -euo pipefail

sudo mkdir -p /opt/shmoobox
sudo mkdir -p /etc/shmoobox

sudo cp /tmp/shmoobox-deploy/app.py /opt/shmoobox/app.py
sudo cp /tmp/shmoobox-deploy/shmoobox-web.service /etc/systemd/system/shmoobox-web.service

if [[ ! -f /etc/shmoobox/config.json ]]; then
  sudo cp /tmp/shmoobox-deploy/config.example.json /etc/shmoobox/config.json
fi

sudo systemctl daemon-reload
sudo systemctl enable shmoobox-web
sudo systemctl restart shmoobox-web

rm -f /tmp/shmoobox-deploy/app.py
rm -f /tmp/shmoobox-deploy/shmoobox-web.service
rm -f /tmp/shmoobox-deploy/config.example.json
rmdir /tmp/shmoobox-deploy 2>/dev/null || true
EOF

echo "Done."
echo "Check status with:"
echo "  ssh $TARGET sudo systemctl status shmoobox-web"
