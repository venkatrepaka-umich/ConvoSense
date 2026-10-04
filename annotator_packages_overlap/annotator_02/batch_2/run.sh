#!/usr/bin/env bash
# Starts the annotation tool. Needs Python 3.
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv || exit 1
  .venv/bin/pip install "potato-annotation==2.9.4" || exit 1
fi
echo "Open http://localhost:8000 in your browser. Press Ctrl+C here when you are done."
.venv/bin/potato start config.yaml -p 8000
