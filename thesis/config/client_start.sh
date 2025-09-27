#!/bin/bash
set -e
SCRIPT_DIR="$(dirname "$(realpath "$0")")/.."
ROOT_DIR="$(realpath "$SCRIPT_DIR/..")"

if [ -z "$1" ]; then
    echo "Please provide a configuration file."
    exit 1
fi

sudo ip netns exec ns1 \
    "$ROOT_DIR/.venv/bin/python" \
    "$ROOT_DIR/thesis/client_session.py" --config "$1"
