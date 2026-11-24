#!/bin/bash
# One-time root setup for the GitHub Actions deploy user.
# Usage, on the VPS, as root:
#   bash install-nova-deploy-user.sh /path/to/nova-deploy-key.pub
# The public key file is the only credential this script reads.
# It does not create passwords and it does not print key material.

set -euo pipefail

if [[ "$(id -u)" != "0" ]]; then
  echo "run this script as root" >&2
  exit 1
fi

pub="${1:-}"
if [[ ! -f "$pub" ]]; then
  echo "pass the path to the deploy public key" >&2
  exit 1
fi
if ! ssh-keygen -l -f "$pub" >/dev/null 2>&1; then
  echo "that file is not an SSH public key" >&2
  exit 1
fi

if ! id nova-deploy >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash nova-deploy
fi
usermod -s /bin/bash nova-deploy
passwd -l nova-deploy >/dev/null || true

install -d -m 700 -o nova-deploy -g nova-deploy /home/nova-deploy/.ssh
install -m 600 -o nova-deploy -g nova-deploy "$pub" /home/nova-deploy/.ssh/authorized_keys
install -d -m 755 -o nova-deploy -g nova-deploy /home/nova-deploy/staging

here=$(cd "$(dirname "$0")" && pwd)
install -m 755 -o root -g root "$here/nova-deploy.sh" /usr/local/sbin/nova-deploy

tmp=$(mktemp)
cat >"$tmp" <<'EOF'
nova-deploy ALL=(root) NOPASSWD: /usr/local/sbin/nova-deploy
EOF
visudo -cf "$tmp"
install -m 440 -o root -g root "$tmp" /etc/sudoers.d/nova-deploy
rm -f "$tmp"
visudo -c >/dev/null

if ! command -v rsync >/dev/null 2>&1; then
  apt-get update
  apt-get install -y rsync
fi

echo "nova-deploy is installed"
echo "sudo is limited to /usr/local/sbin/nova-deploy"
echo "password login for nova-deploy is locked"
