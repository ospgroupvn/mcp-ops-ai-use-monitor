#!/usr/bin/env python3
"""
Debug hook - log everything received from Claude Code
"""

import json
import os
import sys
from datetime import datetime

LOG_FILE = "/tmp/claude_hook_debug.log"

def log(message: str):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {message}\n")
    print(f"[debug-hook] {message}", file=sys.stderr)

def main():
    log("=" * 50)
    log("Stop hook triggered")

    # Log environment variables
    log("Environment variables:")
    for key, value in sorted(os.environ.items()):
        if any(k in key.upper() for k in ['CLAUDE', 'TRANSCRIPT', 'SESSION', 'MCP', 'ANTHROPIC']):
            log(f"  {key}={value[:100]}...")

    # Log stdin
    log("Reading stdin...")
    stdin_data = sys.stdin.read()
    log(f"Stdin length: {len(stdin_data)} chars")
    log(f"Stdin content: {stdin_data[:500]}...")

    if stdin_data.strip():
        try:
            payload = json.loads(stdin_data)
            log("Parsed payload keys: " + str(list(payload.keys())))
            for key, value in payload.items():
                val_str = str(value)[:200] if value else "None"
                log(f"  {key}: {val_str}")
        except json.JSONDecodeError as e:
            log(f"JSON parse error: {e}")

    log("=" * 50)

if __name__ == "__main__":
    main()
