#!/bin/bash
# Apply a staged tree to /opt/nova-export and rebuild containers.
# Installed once as root at /usr/local/sbin/nova-deploy.
# The only argument is the 40-character commit SHA being deployed.
# This script does not print .env, database rows, or credentials.

set -euo pipefail

SHA="${1:-}"
if [[ ! "$SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "refusing deploy: expected a 40-character commit SHA" >&2
  exit 2
fi

STAGING=/home/nova-deploy/staging
DEST=/opt/nova-export
LOCK=/var/lock/nova-export-deploy.lock

if [[ ! -f "$STAGING/docker-compose.prod.yml" || ! -f "$STAGING/apps/api/Dockerfile" ]]; then
  echo "refusing deploy: staging tree is incomplete" >&2
  exit 2
fi
if [[ ! -f "$DEST/.env" ]]; then
  echo "refusing deploy: /opt/nova-export/.env is missing" >&2
  exit 4
fi

mkdir -p /var/lock
exec 9>"$LOCK"
if ! flock -w 900 9; then
  echo "refusing deploy: another deploy holds the lock" >&2
  exit 3
fi

env_before=$(sha256sum "$DEST/.env" | awk '{print $1}')

api_id() {
  docker compose -f "$DEST/docker-compose.prod.yml" ps -q api 2>/dev/null || true
}

volume_of() {
  local cid="$1"
  docker inspect --format '{{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Name}}{{end}}{{end}}' "$cid"
}

cid_before=$(api_id)
if [[ -z "$cid_before" ]]; then
  echo "refusing deploy: api container is not running, so the database volume is not confirmed" >&2
  exit 5
fi
vol_before=$(volume_of "$cid_before")
if [[ -z "$vol_before" ]]; then
  echo "refusing deploy: api container has no /app/data volume" >&2
  exit 5
fi
vol_created_before=$(docker volume inspect "$vol_before" --format '{{.CreatedAt}}')
docker compose -f "$DEST/docker-compose.prod.yml" exec -T api \
  python -c 'import os,sys; p="/app/data/nova.db"; sys.exit(0 if os.path.isfile(p) and os.path.getsize(p)>0 else 1)'

rsync -a --delete --safe-links \
  --exclude '.git/' \
  --exclude 'node_modules/' \
  --exclude 'apps/web/node_modules/' \
  --exclude 'apps/web/.next/' \
  --exclude '__pycache__/' \
  --exclude '.env' \
  --exclude '.env.*' \
  --exclude '*.pem' \
  --exclude 'nova-deploy-key' \
  --exclude 'nova-deploy-key.pub' \
  --exclude 'data/' \
  "$STAGING"/ "$DEST"/

env_after=$(sha256sum "$DEST/.env" | awk '{print $1}')
if [[ "$env_before" != "$env_after" ]]; then
  echo "refusing deploy: .env checksum changed" >&2
  exit 6
fi

cd "$DEST"
export NOVA_REVISION="$SHA"
docker compose -f docker-compose.prod.yml up -d --build

verify_revision() {
  local cid img label
  cid=$(api_id)
  if [[ -z "$cid" ]]; then
    echo "api container is not running" >&2
    return 1
  fi
  img=$(docker inspect --format '{{.Image}}' "$cid")
  label=$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$img")
  [[ "$label" == "$SHA" ]]
}

if ! verify_revision; then
  echo "image revision label did not match; rebuilding without cache" >&2
  docker compose -f docker-compose.prod.yml build --no-cache
  docker compose -f docker-compose.prod.yml up -d
fi
if ! verify_revision; then
  echo "running image revision does not equal $SHA" >&2
  exit 8
fi

cid_after=$(api_id)
vol_after=$(volume_of "$cid_after")
vol_created_after=$(docker volume inspect "$vol_after" --format '{{.CreatedAt}}')
if [[ "$vol_before" != "$vol_after" || "$vol_created_before" != "$vol_created_after" ]]; then
  echo "database volume changed from $vol_before to $vol_after" >&2
  exit 7
fi

ready=0
for _ in $(seq 1 36); do
  if docker compose -f docker-compose.prod.yml exec -T api \
    python -c 'import os,sys,urllib.request; p="/app/data/nova.db"; urllib.request.urlopen("http://127.0.0.1:8000/health"); sys.exit(0 if os.path.isfile(p) and os.path.getsize(p)>0 else 1)'; then
    ready=1
    break
  fi
  sleep 5
done
if [[ "$ready" != "1" ]]; then
  echo "api container health or database file check failed" >&2
  exit 9
fi

echo "deployed $SHA"
echo "database volume $vol_after unchanged"
echo ".env checksum unchanged"
echo "container health ok"
