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
    echo "📁 Logs directory: $LOGS_DIR"
    echo ""
    
    # Check if logs directory exists and has content
    if [ -d "$LOGS_DIR" ] && [ "$(ls -A "$LOGS_DIR" 2>/dev/null)" ]; then
        echo "📊 Existing logs detected in directory:"
        ls -la "$LOGS_DIR" | head -5
        echo ""
        echo "Choose an option:"
        echo "1. Fix permissions preserving existing logs (recommended)"
        echo "2. Remove all logs and recreate directory"
        echo "3. Cancel"
        echo ""
        read -p "Enter your choice (1-3): " choice
        
        case $choice in
            1)
                echo "🔧 Fixing permissions while preserving existing logs..."
                sudo chown -R 1000:1000 "$LOGS_DIR"
                sudo chmod -R 755 "$LOGS_DIR"
                echo "✅ Permissions fixed! Existing logs preserved."
                ;;
            2)
                echo "🗑️  Removing existing logs directory..."
                sudo rm -rf "$LOGS_DIR"
                echo "📁 Creating new logs directory..."
                mkdir -p "$LOGS_DIR"
                echo "👤 Setting ownership to Docker user (1000:1000)..."
                sudo chown 1000:1000 "$LOGS_DIR"
                echo "🔐 Setting proper permissions..."
                chmod 755 "$LOGS_DIR"
                echo "✅ Fresh logs directory created!"
                ;;
            3)
                echo "❌ Operation cancelled."
                exit 0
                ;;
            *)
                echo "❌ Invalid choice. Operation cancelled."
                exit 1
                ;;
        esac
    else
        echo "📁 No existing logs found. Creating fresh directory..."
        # Remove existing logs directory and recreate with proper permissions
        sudo rm -rf "$LOGS_DIR"
        mkdir -p "$LOGS_DIR"
        echo "👤 Setting ownership to Docker user (1000:1000)..."
        sudo chown 1000:1000 "$LOGS_DIR"
        echo "🔐 Setting proper permissions..."
        chmod 755 "$LOGS_DIR"
        echo "✅ Fresh logs directory created!"
    fi
    
    echo ""
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