#!/usr/bin/env bash
# One-time setup for a fresh Ubuntu 22.04/24.04 VM. Run as a sudo-capable user:
#   bash deploy/setup-vm.sh
set -euo pipefail

echo "==> Installing Docker"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo usermod -aG docker "$USER"

echo "==> Adding 2 GB swap (safety net while torch loads four models)"
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo "==> Basic firewall (SSH, HTTP, HTTPS only)"
if command -v ufw >/dev/null 2>&1; then
  sudo ufw allow OpenSSH
  sudo ufw allow 80/tcp
  sudo ufw allow 443/tcp
  sudo ufw --force enable
fi

echo
echo "Done. Log out and back in once so the docker group applies, then:"
echo "  1) copy model checkpoints to deploy/models/  (see deploy/README.md)"
echo "  2) cp deploy/.env.example deploy/.env  and fill it in"
echo "  3) bash deploy/deploy.sh"
