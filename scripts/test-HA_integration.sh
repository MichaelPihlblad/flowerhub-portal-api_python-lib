#!/usr/bin/env bash
set -euo pipefail

# This script tests the local flowerhub-portal-api library against the
# Home Assistant integration to ensure compatibility. It assumes the HA
# integration repo is located at ../flowerhub_homeassistant_integration

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LIBRARY_ROOT="$(dirname "$SCRIPT_DIR")"
HA_REPO_PATH="${LIBRARY_ROOT}/../flowerhub_homeassistant_integration"

# Check if HA integration repo exists
if [[ ! -d "$HA_REPO_PATH" ]]; then
    echo "❌ Home Assistant integration repo not found at: $HA_REPO_PATH"
    echo ""
    echo "Expected structure:"
    echo "  parent_folder/"
    echo "    ├── flowerhub-portal-api_python-lib (this repo)"
    echo "    └── flowerhub_homeassistant_integration (integration repo)"
    echo ""
    echo "Please ensure the integration repo is cloned to: $HA_REPO_PATH"
    exit 1
fi

echo "🔍 Testing library against Home Assistant integration..."
echo ""
echo "Library:  $LIBRARY_ROOT"
echo "Integration: $HA_REPO_PATH"
echo ""

# Check if HA repo has a virtual environment
if [[ ! -d "$HA_REPO_PATH/.venv" ]]; then
    echo "⚠️  Home Assistant integration virtual environment not found."
    echo "   Creating one now..."
    cd "$HA_REPO_PATH"
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -q -r requirements.txt
else
    source "$HA_REPO_PATH/.venv/bin/activate"
fi

# Install test dependencies if missing
if ! python -c "import pytest" >/dev/null 2>&1; then
    echo "📦 Installing test dependencies..."
    pip install -q pytest
fi

# Run integration tests with local library in PYTHONPATH
echo "🧪 Running integration tests..."
echo ""
cd "$HA_REPO_PATH"
export PYTHONPATH="$LIBRARY_ROOT${PYTHONPATH:+:$PYTHONPATH}"
python -m pytest -q

TEST_RESULT=$?

echo ""
if [[ $TEST_RESULT -eq 0 ]]; then
    echo "✅ Integration tests passed!"
    echo ""
    echo "The local library is compatible with the Home Assistant integration."
else
    echo "❌ Integration tests failed!"
    echo ""
    echo "Some integration tests did not pass. Review the output above."
    exit 1
fi
