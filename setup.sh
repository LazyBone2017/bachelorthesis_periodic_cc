#!/bin/bash
set -e

ROOT_DIR="$(dirname "$(realpath "$0")")"

cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

# 2. activate and install deps
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
pip install -r requirements.txt

echo "Environment set up successfully. Execute scripts in /thesis/config to run application."
