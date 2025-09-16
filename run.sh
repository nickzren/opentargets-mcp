#!/bin/bash
# Simple runner script for Open Targets MCP Server
# This makes it easier for non-Python users to run the server

set -euo pipefail

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "uv is not installed. Installing uv..."
    python3 -m pip install --user uv
fi

# Sync dependencies if needed
if [ ! -d ".venv" ]; then
    echo "Setting up virtual environment and dependencies..."
    uv sync
fi

# Run the server
echo "Starting Open Targets MCP Server..."
uv run python -m opentargets_mcp.server
