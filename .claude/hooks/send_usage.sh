#!/bin/bash
# Wrapper script để gọi send_usage.py với proper stdin piping
# Hỗ trợ fallback python3 -> python và cross-platform (macOS, Linux, Windows)

# Get script directory - cross-platform safe
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/send_usage.py"

# Try python3 first, fallback to python
if command -v python3 &> /dev/null; then
    cat | python3 "$PYTHON_SCRIPT"
elif command -v python &> /dev/null; then
    cat | python "$PYTHON_SCRIPT"
else
    echo "[usage-hook ERROR] Neither python3 nor python found in PATH" >&2
    exit 1
fi
