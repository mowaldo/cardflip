#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
if [ ! -f .env ]; then
  token=$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')
  printf 'COMPSAPI_KEY=\nLOCAL_TOKEN=%s\nMONTHLY_LIMIT=100\n' "$token" > .env
  chmod 600 .env
fi
printf '\nSetup complete. Open .env and add your free API key (optional for demo).\nYour local token is in .env. Copy it into the sidebar.\nRun: bash start.sh\n'
