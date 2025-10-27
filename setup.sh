#!/bin/bash
set -e

ROOT_DIR="$(dirname "$(realpath "$0")")"

cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

# activate and install deps
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
pip install -r requirements.txt

if ! python3 -c "import tkinter" &>/dev/null; then
  echo "Installing python3-tk for matplotlib GUI support"
  sudo apt-get update && sudo apt-get install -y python3-tk || echo "Skipping GUI backend (running headless)."
fi

echo "Environment set up successfully. Execute scripts in /thesis/config to run application."
