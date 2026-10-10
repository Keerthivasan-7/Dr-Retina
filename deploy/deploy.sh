#!/usr/bin/env bash
# Build and (re)start the whole backend. Safe to re-run for updates:
#   bash deploy/deploy.sh
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] || { echo "Missing deploy/.env (copy .env.example and fill it in)"; exit 1; }

REQUIRED=(
  models/checkpoints/p0_baseline_resnet50/best.pt
  models/checkpoints/p0_baseline_resnet50/calibration.json
  models/checkpoints/p0_fiqa_effnet_b0/best.pt
  models/checkpoints/p2_lesion_segmentation/best.pt
  models/checkpoints/p2d_lesion_segmentation_v2/best.pt
)
for f in "${REQUIRED[@]}"; do
  [ -f "$f" ] || { echo "Missing model file: deploy/$f (see deploy/README.md)"; exit 1; }
done

set -a; . ./.env; set +a
[ -n "${DOMAIN:-}" ] && [ -n "${AI_SERVICE_KEY:-}" ] || { echo "DOMAIN and AI_SERVICE_KEY must be set in .env"; exit 1; }

echo "==> Building and starting services"
docker compose up -d --build

echo "==> Waiting for health (the AI service needs up to ~2 minutes to load models)"
for i in $(seq 1 40); do
  states=$(docker compose ps --format '{{.Service}}={{.Health}}' | tr '\n' ' ')
  if ! echo "$states" | grep -q "starting"; then break; fi
  sleep 5
done
docker compose ps

echo "==> Public check"
sleep 5
curl -fsS "https://${DOMAIN}/health/ready" && echo || echo "(not reachable yet - DNS or certificate may still be settling; retry in a minute)"

echo
echo "On Vercel set  API_INTERNAL_BASE_URL=https://${DOMAIN}/api/v1  and  APP_URL=${APP_URL}  then redeploy."
