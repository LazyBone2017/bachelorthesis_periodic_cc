#!/bin/bash
set -e
SCRIPT_DIR="$(dirname "$(realpath "$0")")/.."
ROOT_DIR="$(realpath "$SCRIPT_DIR/..")"


if [ -z "$1" ]; then
    echo "Please provide a configuration file."
    exit 1
fi

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

$SUDO_CMD ip netns exec ns1 \
    "$PYTHON_BIN" "$ROOT_DIR/thesis/client_session.py" --config "$1"
