#!/bin/bash

# Game Environment Library Docker Runner Script
# Automatically handles log mounting and provides easy parameter passing

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="$(dirname "$SCRIPT_DIR")/logs"  # Go up one level from scripts/ to project root

# Function to setup logs directory with proper permissions
setup_logs_directory() {
    echo "📁 Setting up logs directory..."
    
    # Check if we're on Linux (where permission issues are common)
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "🐧 Linux detected - checking permissions..."
        
        # If logs directory exists and has permission issues, fix them
        if [ -d "$LOGS_DIR" ]; then
            # Check if we can write to the directory
            if ! [ -w "$LOGS_DIR" ]; then
                echo "⚠️  Permission issue detected. Attempting to fix without data loss..."
                echo "💡 This may require sudo access..."
                
                # Try to fix permissions without deleting existing data
                if sudo chown -R 1000:1000 "$LOGS_DIR" && sudo chmod -R 755 "$LOGS_DIR"; then
                    echo "✅ Permissions fixed successfully! Existing logs preserved."
                else
                    echo "❌ Failed to fix permissions preserving data. You can:"
                    echo "   1. Run: sudo chown -R 1000:1000 logs && sudo chmod -R 755 logs"
                    echo "   2. Or backup logs and run: ./scripts/fix-docker-permissions.sh"
                    exit 1
                fi
            else
                echo "✅ Logs directory permissions are OK"
            fi
        else
            # Create directory with proper permissions
            mkdir -p "$LOGS_DIR"
            if command -v sudo >/dev/null 2>&1; then
                sudo chown 1000:1000 "$LOGS_DIR" 2>/dev/null || true
            fi
            echo "✅ Logs directory created"
        fi
    else
        # On macOS/Windows, just create the directory
        mkdir -p "$LOGS_DIR"
        echo "✅ Logs directory created"
    fi
}

# Setup logs directory
setup_logs_directory

echo ""
echo "🎮 Game Environment Library Docker Runner"
echo "==============================="
echo "📁 Logs will be saved to: $LOGS_DIR"
echo ""

# Change to project root directory
cd "$(dirname "$SCRIPT_DIR")"

# If no arguments provided, show usage
if [ $# -eq 0 ]; then
    echo "🎮 Game Environment Library Docker Runner"
    echo "Usage examples:"
    echo "   ./scripts/run-docker.sh"
    echo "   ./scripts/run-docker.sh python main.py --game pokemon_red --fake-actions --max-steps 50"
    echo "   ./scripts/run-docker.sh python main.py --game pokemon_crystal --fake-actions --lite"
    echo "   ./scripts/run-docker.sh bash"
    echo ""
    echo "🚀 Running with default settings..."
    docker compose run --rm game-env
else
    echo "🚀 Running with custom command: $@"
    docker compose run --rm game-env "$@"
fi 