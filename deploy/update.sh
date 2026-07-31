#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/nis7a}
BRANCH=${BRANCH:-main}
COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.public.yml}

cd "$APP_DIR"
git fetch origin
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"
docker compose -f "$COMPOSE_FILE" up -d --build

echo "NIS7A updated and restarted with $COMPOSE_FILE."
