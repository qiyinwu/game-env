#!/bin/bash

# GBA Game Server Test Runner
# This script sets up a virtual environment and runs all tests

set -e  # Exit on any error

echo "🧪 GBA Game Server Test Runner"
echo "=============================="

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
python -m py_compile tests/test_gba_server.py

# Run the tests
echo "🚀 Running tests..."
echo ""

# Run unit tests
echo "📋 Running unit tests..."
python -m pytest tests/test_gba_server.py::TestGBAGameServer -v

echo ""

# Run integration tests (these require more setup)
echo "🔗 Running integration tests..."
python -m pytest tests/test_gba_server.py::TestGBAClientIntegration -v

echo ""

# Run async tests
echo "⚡ Running async tests..."
python -m pytest tests/test_gba_server.py::test_server_mode_main_function -v

echo ""
echo "✅ All tests completed!"
echo ""
echo "💡 To run tests manually:"
echo "   source venv/bin/activate"
echo "   python -m pytest tests/test_gba_server.py -v"
echo ""
echo "🐳 To test with Docker:"
echo "   docker build -t gba-game-server ."
echo "   docker run -p 8080:8080 gba-game-server --server-mode --headless" 