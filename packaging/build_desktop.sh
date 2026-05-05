#!/usr/bin/env bash
# Build the desktop app bundle (PyInstaller). Run from any directory.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/ui"
npm ci
npm run build
cd "$ROOT"
python3 -m pip install -q pyinstaller
python3 -m pip install -q -e ".[dev,export]"
cd "$ROOT/packaging/pyinstaller"
python3 -m PyInstaller jobshunt.spec
echo ""
echo "Build output: $ROOT/packaging/pyinstaller/dist/"
echo "  macOS: drag JobsHunt.app into /Applications (or open from dist/)."
echo "  Windows: install Inno Setup, open packaging/windows/JobsHunt.iss, press Compile."
