#!/bin/bash
# One-time setup: Python venv and frontend build. Run before deploy/install.sh.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$ROOT"

echo "==> Python environment"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r backend/requirements.txt
echo "    done"

echo "==> Frontend"
cd frontend
npm install --silent
npm run build
cd "$ROOT"

echo
echo "Setup complete. Now run:  sudo bash deploy/install.sh"
