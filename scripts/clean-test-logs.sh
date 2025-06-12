#!/bin/bash

# VideoGameBench Test Log Cleanup Script
# Safely removes test logs without affecting production logs

echo "🧹 VideoGameBench Test Log Cleanup"
echo "=================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TEST_LOGS_DIR="$PROJECT_ROOT/logs/test"

echo "📁 Project root: $PROJECT_ROOT"
echo "🧪 Test logs directory: $TEST_LOGS_DIR"
echo ""

# Check if test logs directory exists
if [ -d "$TEST_LOGS_DIR" ]; then
    echo "📊 Current test logs:"
    du -sh "$TEST_LOGS_DIR"/* 2>/dev/null | head -10 || echo "   (no test logs found)"
    echo ""
    
    echo "This will remove ALL test logs but keep production logs safe."
    echo "Production logs in logs/ (excluding logs/test/) will NOT be affected."
    echo ""
    read -p "Are you sure you want to delete all test logs? (y/N): " confirm
    
    case $confirm in
        [yY]|[yY][eE][sS])
            echo "🗑️  Removing test logs..."
            rm -rf "$TEST_LOGS_DIR"
            echo "✅ Test logs cleaned successfully!"
            echo "📁 Production logs remain untouched in: $PROJECT_ROOT/logs/"
            ;;
        *)
            echo "❌ Operation cancelled."
            ;;
    esac
else
    echo "✅ No test logs directory found. Nothing to clean."
fi

echo ""
echo "💡 Tip: Test logs are automatically created in logs/test/ during testing"
echo "💡 Production logs remain in logs/{game_name}/ and are never auto-deleted" 