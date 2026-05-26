#!/usr/bin/env bash
# quick_setup.sh — Portable venv-first setup bootstrapper.

set -e

# Resolve directory dynamically
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "🤖 Bootstrapping Instagram MCP Setup..."
echo "=========================================="

CANDIDATES=("python3" "python")
FOUND_PY=""

for cmd in "${CANDIDATES[@]}"; do
  if command -v "$cmd" &>/dev/null; then
    if "$cmd" -c "import sys, venv; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
      FOUND_PY="$cmd"
      break
    fi
  fi
done

if [ -z "$FOUND_PY" ]; then
  echo "❌ Error: Suitable Python interpreter not found."
  echo "Requirements:"
  echo "  - Python version >= 3.11"
  echo "  - Standard library 'venv' module installed"
  echo ""
  echo "Please install Python 3.11+ using Homebrew or your system package manager:"
  echo "  macOS:  brew install python@3.12"
  echo "  Ubuntu: sudo apt install python3.12 python3.12-venv"
  exit 1
fi

echo "✓ Detected Python interpreter: $FOUND_PY"
echo "✓ Python version validation passed."
echo "=========================================="

# Run setup.py using the selected validated interpreter path
"$FOUND_PY" setup.py --interpreter "$FOUND_PY"
