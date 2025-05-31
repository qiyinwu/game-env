#!/bin/bash

# VideoGameBench Docker Permissions Fix Script
# Fixes common permission issues on Linux systems

echo "🔧 VideoGameBench Docker Permissions Fix"
echo "========================================"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="$(dirname "$SCRIPT_DIR")/logs"  # Go up one level from scripts/ to project root

# Check if we're on Linux
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "🐧 Linux system detected"
    echo "📁 Fixing permissions for: $LOGS_DIR"
    echo ""
    
    # Remove existing logs directory and recreate with proper permissions
    echo "🗑️  Removing existing logs directory..."
    sudo rm -rf "$LOGS_DIR"
    
    echo "📁 Creating new logs directory..."
    mkdir -p "$LOGS_DIR"
    
    echo "👤 Setting ownership to Docker user (1000:1000)..."
    sudo chown 1000:1000 "$LOGS_DIR"
    
    echo "🔐 Setting proper permissions..."
    chmod 755 "$LOGS_DIR"
    
    echo ""
    echo "✅ Permissions fixed successfully!"
    echo "📊 Directory info:"
    ls -la "$LOGS_DIR"
    echo ""
    echo "🚀 You can now run: ./scripts/run-docker.sh"
    
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "🍎 macOS detected - permission fixes not needed"
    mkdir -p "$LOGS_DIR"
    echo "✅ Logs directory ready"
    
else
    echo "❓ Unknown OS: $OSTYPE"
    echo "💡 This script is designed for Linux systems"
    echo "📁 Creating logs directory anyway..."
    mkdir -p "$LOGS_DIR"
fi 