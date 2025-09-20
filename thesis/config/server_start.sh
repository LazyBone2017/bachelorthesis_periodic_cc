#!/bin/bash
set -e
SCRIPT_DIR="$(dirname "$(realpath "$0")")/.."
ROOT_DIR="$(realpath "$SCRIPT_DIR/..")"

sudo ip netns exec ns2 \
    "$ROOT_DIR/.venv/bin/python" \
    "$ROOT_DIR/thesis/server_app.py"
