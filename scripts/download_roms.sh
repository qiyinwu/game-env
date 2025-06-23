#!/bin/bash

# Game Environment Library ROM Download Script
# This script downloads legal, open-source ROM files for testing

echo "🎮 Game Environment Library ROM Download Script"
echo "=============================================="

# Get the project root directory (one level up from scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ROMS_DIR="$PROJECT_ROOT/roms"

# Change to project root directory
cd "$PROJECT_ROOT"

# Create roms directory if it doesn't exist
mkdir -p "$ROMS_DIR"

# Download Pokemon Red ROM (legal open-source version)
echo "📥 Downloading Pokemon Red ROM..."
if curl -L -o "$ROMS_DIR/pokemon_red.gb" "https://github.com/x1qqDev/pokemon-red/raw/main/Pokemon.gb"; then
    echo "✅ Pokemon Red ROM downloaded successfully!"
    echo "📊 File size: $(ls -lh "$ROMS_DIR/pokemon_red.gb" | awk '{print $5}')"
else
    echo "❌ Failed to download Pokemon Red ROM"
    exit 1
fi

# Verify ROM file
if [ -f "$ROMS_DIR/pokemon_red.gb" ]; then
    file_size=$(stat -f%z "$ROMS_DIR/pokemon_red.gb" 2>/dev/null || stat -c%s "$ROMS_DIR/pokemon_red.gb" 2>/dev/null)
    if [ "$file_size" -eq 1048576 ]; then
        echo "✅ ROM file verification passed (1MB)"
    else
        echo "⚠️  ROM file size unexpected: $file_size bytes"
    fi
else
    echo "❌ ROM file not found after download"
    exit 1
fi

echo ""
echo "🚀 Ready to test! You can now run:"
echo "   python main.py --game pokemon_red --fake-actions --lite --max-steps 10"
echo ""
echo "📁 ROM files location: $ROMS_DIR/"
ls -la "$ROMS_DIR/" 