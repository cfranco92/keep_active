#!/bin/bash
# keep_active.sh — Launches the cross-platform Python implementation (macOS / Windows use python directly).
# Usage: ./keep_active.sh [interval_seconds]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/keep_active.py" "$@"
