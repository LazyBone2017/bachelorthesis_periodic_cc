#!/bin/bash
set -e
SCRIPT_DIR="$(dirname "$(realpath "$0")")/.."
ROOT_DIR="$(realpath "$SCRIPT_DIR/..")"

sudo ip netns exec ns1 \
    "$ROOT_DIR/.venv/bin/python" \
    "$ROOT_DIR/thesis/live_monitor.py"
