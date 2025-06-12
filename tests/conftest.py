#!/usr/bin/env python3
"""
Pytest configuration for videogame benchmark tests

This file configures pytest for the entire test suite, including:
- Test markers for categorization
- Fixtures for common test setup
- Command line options
- Test discovery settings
"""

import pytest
import sys
import os
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock
from PIL import Image

# Add src to path for all tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def pytest_configure(config):
    """Configure pytest with custom markers"""
    # Only keep essential markers
    config.addinivalue_line("markers", "unit: Unit tests - fast, isolated, minimal dependencies")
    config.addinivalue_line("markers", "integration: Integration tests - medium speed, real components")
    config.addinivalue_line("markers", "e2e: End-to-end tests - full system testing")


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on command line options"""
    if not config.getoption("--run-e2e"):
        skip_e2e = pytest.mark.skip(reason="need --run-e2e option to run")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e)


@pytest.fixture(scope="session")
def test_data_dir():
    """Provide path to test data directory"""
    return Path(__file__).parent / "test_data"


@pytest.fixture(scope="session")
def temp_logs_dir():
    """Provide a temporary directory for test logs"""
    with tempfile.TemporaryDirectory(prefix="test_logs_") as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def cleanup_test_logs():
    """Cleanup test logs after each test"""
    yield
    # Cleanup any test logs that might have been created
    test_log_dirs = [
        Path("logs/test"),
        Path("logs/unit_test"),
        Path("logs/integration_test"),
        Path("logs/e2e_test"),
        Path("test_logs"),  # Add root level test_logs cleanup
    ]
    
    for log_dir in test_log_dirs:
        if log_dir.exists():
            shutil.rmtree(log_dir, ignore_errors=True)


def pytest_sessionfinish(session, exitstatus):
    """Cleanup session-level artifacts after all tests complete"""
    # Clean up any remaining test artifacts
    cleanup_paths = [
        Path("test_logs"),
        Path("logs/test"),
        Path("logs/unit_test"), 
        Path("logs/integration_test"),
        Path("logs/e2e_test"),
        Path("real_integration_test_storage"),  # Also cleanup this if it exists
    ]
    
    for path in cleanup_paths:
        if path.exists():
            try:
                shutil.rmtree(path, ignore_errors=True)
                print(f"\n🧹 Cleaned up {path}")
            except Exception as e:
                print(f"\n⚠️  Could not clean up {path}: {e}")


def pytest_addoption(parser):
    """Add custom command line options"""
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="Run end-to-end tests"
    )
    parser.addoption(
        "--quick",
        action="store_true",
        default=False,
        help="Run only quick tests (unit + fast integration)"
    )


def pytest_runtest_setup(item):
    """Skip tests based on command line options"""
    if item.config.getoption("--quick"):
        # In quick mode, skip e2e tests
        if "e2e" in item.keywords:
            pytest.skip("skipped in quick mode: e2e")


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Add custom summary information"""
    if hasattr(terminalreporter, 'stats'):
        passed = len(terminalreporter.stats.get('passed', []))
        failed = len(terminalreporter.stats.get('failed', []))
        skipped = len(terminalreporter.stats.get('skipped', []))
        
        terminalreporter.write_sep("=", "Test Summary")
        terminalreporter.write_line(f"✅ Passed: {passed}")
        terminalreporter.write_line(f"❌ Failed: {failed}")
        terminalreporter.write_line(f"⏸️  Skipped: {skipped}")
        
        if config.getoption("--quick"):
            terminalreporter.write_line("🚀 Quick mode: Only fast tests were run")
        
        if not config.getoption("--run-e2e"):
            terminalreporter.write_line("💡 Tip: Use --run-e2e to run end-to-end tests") 