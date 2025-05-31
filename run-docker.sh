#!/bin/bash

# VideoGameBench Docker Runner Script
# Automatically handles log mounting and provides easy parameter passing

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="$SCRIPT_DIR/logs"

# Create logs directory if it doesn't exist
mkdir -p "$LOGS_DIR"

echo "🎮 VideoGameBench Docker Runner"
echo "==============================="
echo "📁 Logs will be saved to: $LOGS_DIR"
echo ""

# Default Docker run command with log mounting
DOCKER_CMD="docker run --rm -it -v \"$LOGS_DIR:/app/logs\" videogamebench"

# If no arguments provided, show usage
if [ $# -eq 0 ]; then
    echo "Usage examples:"
    echo ""
    echo "1. Run with default settings (20 steps, fake actions):"
    echo "   ./run-docker.sh"
    echo ""
    echo "2. Run with custom parameters:"
    echo "   ./run-docker.sh python main.py --game pokemon_red --fake-actions --max-steps 50"
    echo ""
    echo "3. Run with different game:"
    echo "   ./run-docker.sh python main.py --game pokemon_crystal --fake-actions --lite"
    echo ""
    echo "4. Run interactive shell:"
    echo "   ./run-docker.sh bash"
    echo ""
    echo "🚀 Running with default settings..."
    eval $DOCKER_CMD
else
    echo "🚀 Running with custom command: $@"
    eval "$DOCKER_CMD $@"
fi 