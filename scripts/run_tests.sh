#!/bin/bash

# Game Environment Library Test Runner
# This script sets up a virtual environment and runs all tests

set -e  # Exit on any error

echo "🧪 Game Environment Library Test Runner"
echo "===================================="

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Install test dependencies if not already in requirements.txt
echo "🧪 Installing test dependencies..."
pip install pytest pytest-asyncio

# Run syntax check first
echo "✅ Running syntax checks..."
python -m py_compile src/emulators/gba/game_server.py
python -m py_compile examples/gba_client_example.py

# Run the tests
echo "🚀 Running tests..."
echo ""

# Run unit tests
echo "📋 Running unit tests..."
python -m pytest tests/unit/ -v

echo ""

# Run integration tests
echo "🔗 Running integration tests..."
python -m pytest tests/integration/ -v

echo ""

# Run E2E tests
echo "🌐 Running E2E tests..."
python -m pytest tests/e2e/ -v

echo ""
echo "✅ All tests completed!"
echo ""
echo "💡 To run tests manually:"
echo "   source venv/bin/activate"
echo "   python -m pytest tests/ -v"
echo ""
echo "🐳 To test with Docker:"
echo "   docker build -t game-env ."
echo "   docker run -p 8080:8080 game-env --server-mode --headless" 