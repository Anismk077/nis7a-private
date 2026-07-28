#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/nis7a}
BRANCH=${BRANCH:-main}

cd "$APP_DIR"
git fetch origin
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"
docker compose up -d --build

echo "NIS7A updated and restarted."
