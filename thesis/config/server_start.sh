#!/bin/bash
set -e

SCRIPT_DIR="$(dirname "$(realpath "$0")")/.."
ROOT_DIR="$(realpath "$SCRIPT_DIR/..")"

if [ -f /.dockerenv ]; then
    IS_DOCKER=true
else
    IS_DOCKER=false
fi

if [ "$IS_DOCKER" = true ]; then
    PYTHON_BIN="python3"
else
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
fi

SUDO_CMD=""
if [ "$EUID" -ne 0 ]; then
    SUDO_CMD="sudo"
fi

$SUDO_CMD ip netns exec ns2 \
    "$PYTHON_BIN" "$ROOT_DIR/thesis/server_app.py"
