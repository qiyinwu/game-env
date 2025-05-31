#!/bin/bash

# VideoGameBench Docker Entrypoint Script
# This script handles log mounting and parameter passing

echo "🎮 VideoGameBench Docker Container"
echo "=================================="

# Check if logs directory is mounted
if [ -d "/app/logs" ] && [ "$(ls -A /app/logs 2>/dev/null)" ]; then
    echo "📁 Logs directory is mounted and contains data"
elif [ -d "/app/logs" ]; then
    echo "📁 Logs directory is mounted (empty)"
else
    echo "📁 Logs directory not mounted - logs will be lost when container exits"
    echo "💡 To persist logs, run with: docker run -v \$(pwd)/logs:/app/logs ..."
fi

# Check if ROM exists
if [ -f "/app/roms/pokemon_red.gb" ]; then
    echo "🎮 Pokemon Red ROM found ($(stat -c%s /app/roms/pokemon_red.gb 2>/dev/null || stat -f%z /app/roms/pokemon_red.gb) bytes)"
else
    echo "❌ Pokemon Red ROM not found!"
    exit 1
fi

echo "🚀 Starting VideoGameBench..."
echo "Command: $@"
echo ""

# If no arguments provided, use default
if [ $# -eq 0 ]; then
    echo "Using default command: python main.py --game pokemon_red --fake-actions --lite --max-steps 20"
    exec python main.py --game pokemon_red --fake-actions --lite --max-steps 20
else
    # Execute the provided command
    exec "$@"
fi 