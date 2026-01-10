#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
# Install test dependencies if missing
if ! python -c "import pytest" >/dev/null 2>&1; then
  pip install -r dev-requirements.txt
fi
python -m pytest -q
