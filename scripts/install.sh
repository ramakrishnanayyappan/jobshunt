#!/usr/bin/env bash
# JobsHunt unified installer entry (Linux/macOS). Runs prerequisite bootstrap, then install.py.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$(basename "$SCRIPT_DIR")" == "scripts" ]]; then
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  REPO_ROOT="$SCRIPT_DIR"
fi
cd "$REPO_ROOT"

python_ok() {
  command -v python3 >/dev/null 2>&1 || return 1
  python3 -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 9) else 1)' 2>/dev/null
}

if ! python_ok; then
  if command -v apt-get >/dev/null 2>&1; then
    echo "[install] Bootstrap: installing Python via apt-get (sudo may prompt)..."
    sudo apt-get update -qq
    sudo apt-get install -y python3 python3-venv python3-pip
  elif [[ "$(uname -s)" == "Darwin" ]] && command -v brew >/dev/null 2>&1; then
    echo "[install] Bootstrap: installing Python via Homebrew..."
    brew install python@3.12 || brew upgrade python@3.12 || true
  fi
fi

if ! python_ok; then
  echo "[install] ERROR: Need Python 3.9+ on PATH (python3). Install Python, then re-run:"
  echo "  $0 $*"
  exit 1
fi

exec python3 "${REPO_ROOT}/install.py" "$@"
