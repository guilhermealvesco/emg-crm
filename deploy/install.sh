#!/usr/bin/env bash
# Instalação do EMG CRM na VPS (Ubuntu/Debian). Rode como root:
#   bash deploy/install.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo ">> Instalando Docker..."
  curl -fsSL https://get.docker.com | sh
fi
docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 não encontrado. Instale o plugin docker-compose-plugin."; exit 1; }

if [ ! -f .env ]; then
  cp .env.example .env
  sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$(openssl rand -hex 32)/" .env
  sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 16)/" .env
  echo ">> .env criado. EDITE AGORA: nano .env  (PUBLIC_URL, CRM_DOMAIN, tokens APIBrasil/Autentique) e rode este script de novo."
  exit 0
fi

mkdir -p storage/contratos
echo ">> Subindo containers..."
docker compose up -d --build
echo ">> Aguardando o app..."
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8019/health >/dev/null 2>&1; then break; fi
  sleep 2
done
echo ">> Criando tabelas e usuários iniciais..."
docker compose exec -T app python -m scripts.seed
echo
echo ">> Pronto. Acesse: $(grep ^PUBLIC_URL .env | cut -d= -f2)"
echo "   Logs: docker compose logs -f app"
