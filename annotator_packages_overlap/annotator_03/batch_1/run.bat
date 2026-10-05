@echo off
rem Starts the annotation tool. Needs Python 3.
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv || exit /b 1
  .venv\Scripts\pip install "potato-annotation==2.9.4" || exit /b 1
)
echo Open http://localhost:8000 in your browser. Press Ctrl+C here when you are done.
.venv\Scripts\potato start config.yaml -p 8000
