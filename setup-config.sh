#!/bin/bash
# Quick setup script for Plex MCP Server configuration

cd "$(dirname "$0")"

echo "🎬 Plex MCP Server - Quick Configuration"
echo ""
echo "This will launch an interactive wizard to configure your server."
echo ""

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo "❌ 'uv' not found. Please install it first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.11 or higher."
    exit 1
fi

# Run configuration script
echo "Starting configuration wizard..."
echo ""

uv run python configure.py

exit $?
