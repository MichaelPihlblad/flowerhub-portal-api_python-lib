#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -d .venv ]]; then
  source .venv/bin/activate
fi
if ! command -v pre-commit >/dev/null 2>&1; then
  pip install pre-commit
fi
pre-commit run --all-files
