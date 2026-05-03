#!/bin/bash
set -e

REPO_DIR="/home/deploy/barbershop-chatbot"

echo "[deploy] $(date): iniciando deploy..."
cd "$REPO_DIR"
git pull origin main
docker compose up -d --build
echo "[deploy] $(date): deploy concluído."
