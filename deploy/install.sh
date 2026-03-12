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

ssh "$TARGET" sudo mkdir -p /opt/shmoobox/app /opt/shmoobox/config
ssh "$TARGET" sudo chown -R bear:bear /opt/shmoobox
ssh "$TARGET" sudo mkdir -p /etc/shmoobox
ssh "$TARGET" mkdir -p /tmp/shmoobox-deploy

rsync -av "$REPO_ROOT/app/" "$TARGET:/opt/shmoobox/app/"
rsync -av "$REPO_ROOT/config/" "$TARGET:/opt/shmoobox/config/"
rsync -av "$REPO_ROOT/deploy/shmoobox-web.service" "$TARGET:/tmp/shmoobox-deploy/shmoobox-web.service"

ssh "$TARGET" 'bash -s' <<'EOF'
set -euo pipefail

sudo cp /tmp/shmoobox-deploy/shmoobox-web.service /etc/systemd/system/shmoobox-web.service

if [[ ! -f /etc/shmoobox/config.json ]]; then
  sudo cp /tmp/shmoobox-deploy/config.example.json /etc/shmoobox/config.json
fi

sudo systemctl daemon-reload
sudo systemctl enable shmoobox-web
sudo systemctl restart shmoobox-web

rm -f /tmp/shmoobox-deploy/shmoobox-web.service
rmdir /tmp/shmoobox-deploy 2>/dev/null || true
EOF

echo "Done."
echo "Check status with:"
echo "  ssh $TARGET sudo systemctl status shmoobox-web"
