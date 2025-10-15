#!/bin/bash
set -e

SCRIPT_DIR="$(dirname "$(realpath "$0")")/.."
ROOT_DIR="$(realpath "$SCRIPT_DIR/..")"

# --- Detect runtime environment ---
# Docker containers usually have /.dockerenv or the hostname equals container ID
if [ -f /.dockerenv ]; then
    IS_DOCKER=true
else
    IS_DOCKER=false
fi

# --- Select Python binary ---
if [ "$IS_DOCKER" = true ]; then
    PYTHON_BIN="python3"
else
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
fi

# --- Select sudo (only outside Docker, if not root) ---
SUDO_CMD=""
if [ "$EUID" -ne 0 ]; then
    SUDO_CMD="sudo"
fi

# --- Main execution ---
$SUDO_CMD ip netns exec ns2 \
    "$PYTHON_BIN" "$ROOT_DIR/thesis/server_app.py"
