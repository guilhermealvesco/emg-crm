#!/usr/bin/env bash
# Atualiza o CRM a partir do GitHub e reinicia. Rode na VPS: bash deploy/update.sh
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
docker compose up -d --build app
docker compose exec -T app python -m scripts.seed >/dev/null || true
curl -fsS http://127.0.0.1:8010/health && echo
