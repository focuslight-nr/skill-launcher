#!/usr/bin/env bash
# skill-launcher launcher: creates/uses its own .venv, installs deps, starts the server.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -d .venv ]; then
  echo "[start.sh] creating venv..."
  python3 -m venv .venv
fi

./.venv/bin/pip install --quiet -r requirements.txt

exec ./.venv/bin/python server.py "$@"
