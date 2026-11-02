#!/usr/bin/env bash
# Instalação do zero na VPS (Ubuntu/Debian), em um único comando.
# Variáveis esperadas no ambiente: REPO (ssh url), DEPLOY_KEY_B64, CRM_DOMAIN, APIBRASIL_TOKEN, AUTENTIQUE_TOKEN,
# opcionalmente AUTENTIQUE_WEBHOOK_SECRET, GUILHERME_PASSWORD, EDUARDA_PASSWORD.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
DIR=/root/emg-crm

echo ">> Pacotes base"
apt-get update -qq && apt-get install -y -qq git curl openssl ca-certificates >/dev/null

echo ">> Chave de deploy (somente leitura no repositório)"
mkdir -p /root/.ssh && chmod 700 /root/.ssh
echo "$DEPLOY_KEY_B64" | base64 -d > /root/.ssh/emg_crm_deploy && chmod 600 /root/.ssh/emg_crm_deploy
touch /root/.ssh/config && chmod 600 /root/.ssh/config
if ! grep -q "Host github.com-emg" /root/.ssh/config; then
cat >> /root/.ssh/config <<CFG
Host github.com-emg
  HostName github.com
  User git
  IdentityFile /root/.ssh/emg_crm_deploy
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
CFG
fi

echo ">> Código"
if [ -d "$DIR/.git" ]; then git -C "$DIR" pull --ff-only; else git clone "${REPO/github.com/github.com-emg}" "$DIR"; fi
cd "$DIR"

echo ">> Docker"
command -v docker >/dev/null 2>&1 || curl -fsSL https://get.docker.com | sh
docker compose version >/dev/null

echo ">> Firewall (22, 80, 443)"
if command -v ufw >/dev/null 2>&1; then ufw allow 22/tcp >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null; yes | ufw enable >/dev/null || true; fi

if [ ! -f .env ]; then
  echo ">> .env"
  cp .env.example .env
  sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$(openssl rand -hex 32)|" .env
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(openssl rand -hex 16)|" .env
  sed -i "s|^PUBLIC_URL=.*|PUBLIC_URL=https://${CRM_DOMAIN}|" .env
  sed -i "s|^CRM_DOMAIN=.*|CRM_DOMAIN=${CRM_DOMAIN}|" .env
  sed -i "s|^APIBRASIL_TOKEN=.*|APIBRASIL_TOKEN=${APIBRASIL_TOKEN:-}|" .env
  sed -i "s|^AUTENTIQUE_TOKEN=.*|AUTENTIQUE_TOKEN=${AUTENTIQUE_TOKEN:-}|" .env
  sed -i "s|^AUTENTIQUE_WEBHOOK_SECRET=.*|AUTENTIQUE_WEBHOOK_SECRET=${AUTENTIQUE_WEBHOOK_SECRET:-}|" .env
  sed -i "s|^GUILHERME_PASSWORD=.*|GUILHERME_PASSWORD=${GUILHERME_PASSWORD:-}|" .env
  sed -i "s|^EDUARDA_PASSWORD=.*|EDUARDA_PASSWORD=${EDUARDA_PASSWORD:-}|" .env
  chmod 600 .env
fi

mkdir -p storage/contratos
# Caddy (HTTPS) só se as portas 80/443 estiverem livres; senão, outro proxy da VPS deve apontar para 127.0.0.1:8019
if ss -ltn 2>/dev/null | grep -qE ':(80|443)\s'; then
  echo ">> Portas 80/443 já em uso nesta VPS: subindo sem o Caddy. Aponte o proxy existente (${CRM_DOMAIN}) para http://127.0.0.1:8019"
  export COMPOSE_PROFILES=""
else
  export COMPOSE_PROFILES="caddy"
fi
grep -q '^COMPOSE_PROFILES=' .env && sed -i "s|^COMPOSE_PROFILES=.*|COMPOSE_PROFILES=${COMPOSE_PROFILES}|" .env || echo "COMPOSE_PROFILES=${COMPOSE_PROFILES}" >> .env
echo ">> Subindo containers (pode levar alguns minutos na primeira vez)"
docker compose up -d --build
for i in $(seq 1 60); do curl -fsS http://127.0.0.1:8019/health >/dev/null 2>&1 && break; sleep 2; done
curl -fsS http://127.0.0.1:8019/health >/dev/null || { echo "app não respondeu; veja: docker compose logs app"; exit 1; }

echo ">> Usuários iniciais"
docker compose exec -T app python -m scripts.seed

echo ">> Backup diário às 03:00"
( crontab -l 2>/dev/null | grep -v emg-crm/deploy/backup.sh; echo "0 3 * * * bash $DIR/deploy/backup.sh >> /var/log/emg-backup.log 2>&1" ) | crontab -

echo
echo "================================================================"
echo " EMG CRM no ar: https://${CRM_DOMAIN}"
echo " (o certificado HTTPS é emitido automaticamente assim que o DNS apontar para esta VPS)"
echo " Logs: cd $DIR && docker compose logs -f app"
echo "================================================================"
