#!/usr/bin/env bash
# Bootstraps a local (non-Docker) development environment:
# Python venv + editable installs, pnpm install, and a .env file.
#
# For a Docker-only workflow you don't need this script — see the
# "Docker Compose" section of the root README instead.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [ ! -f .env ]; then
  echo "Creating .env from .env.example"
  cp .env.example .env
fi

echo "Setting up Python environment (.venv)..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -e packages/llm -e packages/shared -e "apps/api[dev]" -q

echo "Installing frontend dependencies (pnpm)..."
corepack enable
corepack pnpm install

cat <<'EOF'

Setup complete.

Next steps:
  docker compose up -d db                                   # start Postgres
  source .venv/bin/activate
  alembic -c apps/api/alembic.ini upgrade head               # run migrations
  uvicorn app.main:app --app-dir apps/api --reload           # start the API
  pnpm --filter web dev                                      # start the frontend (new shell)
EOF
