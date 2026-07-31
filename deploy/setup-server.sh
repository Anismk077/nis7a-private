#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/nis7a}
REPO_URL=${REPO_URL:-https://github.com/Anismk077/nis7a-private.git}
BRANCH=${BRANCH:-main}
COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.public.yml}

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker first."
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "Git is required. Install git first."
  exit 1
fi

sudo mkdir -p "$APP_DIR"
sudo chown -R "$USER":"$USER" "$APP_DIR"

if [ ! -d "$APP_DIR/.git" ]; then
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" fetch origin
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
fi

cd "$APP_DIR"
docker compose -f "$COMPOSE_FILE" up -d --build

echo "NIS7A is running publicly with $COMPOSE_FILE."
