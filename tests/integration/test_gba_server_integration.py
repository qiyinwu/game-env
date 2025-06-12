#!/usr/bin/env python3
"""
Integration tests for GBA Game Server

Tests cover:
- Component integration without external dependencies
- Game server and interface coordination  
- Action processing workflow
- State management across components
- Server logic integration

Mocks external dependencies (GBAInterface, HTTP server) but tests real component interactions.
"""

import pytest
import sys
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
import shutil

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.emulators.gba.game_server import GBAGameServer


def cleanup_test_logs(log_dir):
    """
    Clean up test log directories and empty parent directories.
    Only cleans up directories under logs/test/ for safety.
    """
    if not log_dir or not log_dir.exists():
        return
    
    # Safety check - only clean up test directories
    log_dir_str = str(log_dir)
    if "logs/test" not in log_dir_str:
        return
    
    # Remove the specific test directory
    shutil.rmtree(log_dir, ignore_errors=True)
    
    # Clean up empty parent directories up to and including logs/test/
    current_dir = log_dir.parent
    while current_dir and "logs/test" in str(current_dir):
        try:
            # Only remove if directory is empty
            if current_dir.exists() and not any(current_dir.iterdir()):
                current_dir.rmdir()
                # If we just removed logs/test, we're done
                if current_dir.name == "test":
                    break
                current_dir = current_dir.parent
            else:
                break
        except (OSError, PermissionError):
            # Directory not empty or permission denied, stop cleanup
            break


@pytest.mark.integration
class TestGBAServerGameIntegration:
    """Test game server integration - real component interactions with minimal mocking"""
    
    @pytest.fixture
    def mock_gba_interface(self):
        """Mock only the external GBAInterface dependency"""
        with patch('src.emulators.gba.game_server.GBAInterface') as mock_interface_class:
            mock_interface = Mock()
            mock_interface.load_game.return_value = True
            
            # Create test images for different states
            initial_screen = Image.new('RGB', (160, 144), 'green')
            action_screen = Image.new('RGB', (160, 144), 'blue')
            
            mock_interface.get_observation.return_value = {
                'screen': initial_screen,
                'buttons': ['A', 'B', 'START', 'SELECT', 'UP', 'DOWN', 'LEFT', 'RIGHT']
            }
            mock_interface.step.return_value = (
                {'screen': action_screen, 'buttons': []},
                0,  # reward
                False,  # done
                {}  # info
            )
            mock_interface.reset.return_value = {
                'screen': initial_screen,
                'buttons': []
            }
            mock_interface.close = Mock()
            
            mock_interface_class.return_value = mock_interface
            yield mock_interface
    
    @pytest.fixture
    def integration_server(self, mock_gba_interface):
        """Server for integration testing with real HTTP components"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "integration_test"
            # Use port 0 to let system assign free port
            server = GBAGameServer(port=0, log_dir=log_dir, game_name="integration_test")
            yield server
            if server.is_running:
                server.stop()
    
    def test_server_startup_integration(self, integration_server, mock_gba_interface):
        """Test server startup integrates all components correctly"""
        server = integration_server
        
        with tempfile.NamedTemporaryFile(suffix='.gba', delete=False) as temp_rom:
            temp_rom.write(b"fake rom data")
            temp_rom_path = temp_rom.name
        
        try:
            url = server.start(temp_rom_path)
            
            # Verify game interface integration
            assert server.game_interface is not None
            mock_gba_interface.load_game.assert_called_once_with(temp_rom_path)
            mock_gba_interface.get_observation.assert_called_once()
            
            # Verify server state integration
            assert server.is_running
            assert server.game_state == "ready"
            assert len(server.screenshot_history) == 1
            assert server.step_count == 0
            
            # Verify real HTTP server integration
            assert server.server is not None  # Real HTTP server instance
            assert server.port > 0  # Real port assigned
            assert url == f"http://localhost:{server.port}"
            
            # Verify that HTTP thread is actually running
            assert hasattr(server, 'server_thread')
            assert server.server_thread.is_alive()
            
        finally:
            server.stop()
            os.unlink(temp_rom_path)
    
    def test_action_processing_integration(self, integration_server, mock_gba_interface):
        """Test action processing integrates parsing, execution, and state updates"""
        server = integration_server
        
        with tempfile.NamedTemporaryFile(suffix='.gba', delete=False) as temp_rom:
            temp_rom.write(b"fake rom data")
            temp_rom_path = temp_rom.name
        
        try:
            server.start(temp_rom_path)
            
            # Test action processing integration
            actions = ["A", "B", "A,B", "UP,DOWN,LEFT,RIGHT"]
            result = server._execute_actions(actions)
            
            # Verify parsing integration
            assert result["success"] is True
            assert result["total_actions"] == 4
            assert len(result["results"]) == 4
            
            # Verify each action was processed
            expected_actions = ["A", "B", "A,B", "UP,DOWN,LEFT,RIGHT"]
            for i, expected_action in enumerate(expected_actions):
                assert result["results"][i]["action"] == expected_action
                assert result["results"][i]["success"] is True
            
            # Verify state integration
            assert server.step_count == 4
            assert server.game_state == "playing"
            assert len(server.screenshot_history) == 5  # initial + 4 actions
            
            # Verify interface integration
            assert mock_gba_interface.step.call_count == 4
            
        finally:
            server.stop()
            os.unlink(temp_rom_path)
    
    def test_error_handling_integration(self, integration_server, mock_gba_interface):
        """Test error handling integrates across components"""
        server = integration_server
        
        # Test ROM loading failure integration
        mock_gba_interface.load_game.return_value = False
        
        with pytest.raises(RuntimeError, match="Failed to load ROM"):
            server.start("nonexistent.gba")
        
        # Verify failure state - game_interface is created but ROM load failed
        assert not server.is_running
        # Note: game_interface is created during start() but ROM loading failed
        # So it exists but the server is not running
        
        # Test action execution failure integration
        mock_gba_interface.load_game.return_value = True
        mock_gba_interface.step.side_effect = Exception("Interface error")
        
        with tempfile.NamedTemporaryFile(suffix='.gba', delete=False) as temp_rom:
            temp_rom.write(b"fake rom data")
            temp_rom_path = temp_rom.name
        
        try:
            server.start(temp_rom_path)
            
            # Action should fail gracefully
            result = server._execute_actions(["A"])
            assert result["success"] is True
            assert result["results"][0]["success"] is False
            assert "error" in result["results"][0]
            
        finally:
            server.stop()
            os.unlink(temp_rom_path)
    
    def test_state_persistence_integration(self, integration_server, mock_gba_interface):
        """Test state persistence across multiple operations"""
        server = integration_server
        
        with tempfile.NamedTemporaryFile(suffix='.gba', delete=False) as temp_rom:
            temp_rom.write(b"fake rom data")
            temp_rom_path = temp_rom.name
        
        try:
            server.start(temp_rom_path)
            
            # Execute multiple action batches
            server._execute_actions(["A", "B"])
            assert server.step_count == 2
            assert len(server.screenshot_history) == 3
            
            server._execute_actions(["UP", "DOWN"])
            assert server.step_count == 4
            assert len(server.screenshot_history) == 5
            
            # Test screenshot history limit
            server.max_screenshot_history = 3
            server._execute_actions(["A"])
            assert len(server.screenshot_history) == 3  # Should be trimmed
            assert server.step_count == 5
            
        finally:
            server.stop()
            os.unlink(temp_rom_path)
    
    def test_server_lifecycle_integration(self, integration_server, mock_gba_interface):
        """Test complete server lifecycle integration"""
        server = integration_server
        
        with tempfile.NamedTemporaryFile(suffix='.gba', delete=False) as temp_rom:
            temp_rom.write(b"fake rom data")
            temp_rom_path = temp_rom.name
        
        try:
            # Test startup
            assert not server.is_running
            url = server.start(temp_rom_path)
            assert server.is_running
            assert server.game_state == "ready"
            
            # Test double start (should be idempotent)
            url2 = server.start(temp_rom_path)
            assert url == url2
            assert mock_gba_interface.load_game.call_count == 1  # Only called once
            
            # Test operation
            server._execute_actions(["A"])
            assert server.game_state == "playing"
            assert server.step_count == 1
            
            # Test stop
            server.stop()
            assert not server.is_running
            mock_gba_interface.close.assert_called_once()
            
        finally:
            if server.is_running:
                server.stop()
            os.unlink(temp_rom_path)


@pytest.mark.integration
class TestGBAServerLogDirectoryIntegration:
    """Test log directory creation and management integration"""
    
    def test_log_directory_creation_integration(self):
        """Test log directory is created when needed"""
        test_log_dir = Path("logs/test/log_integration") / f"test_{int(time.time() * 1000)}"
        
        with patch('src.emulators.gba.game_server.GBAInterface') as mock_interface_class:
            mock_interface = Mock()
            mock_interface.load_game.return_value = True
            mock_interface.get_observation.return_value = {
                'screen': Image.new('RGB', (160, 144), 'red')
            }
            mock_interface_class.return_value = mock_interface
            
            server = GBAGameServer(port=0, log_dir=test_log_dir)
            
            # Mock HTTP server
            with patch('socketserver.TCPServer'), patch('threading.Thread'):
                with tempfile.NamedTemporaryFile(suffix='.gba', delete=False) as temp_rom:
                    temp_rom.write(b"fake rom data")
                    temp_rom_path = temp_rom.name
                
                try:
                    # Directory shouldn't exist yet
                    assert not test_log_dir.exists()
                    
                    # Start server - should create log directory
                    server.start(temp_rom_path)
                    assert test_log_dir.exists()
                    assert (test_log_dir / "game_screen").exists()
                    
                finally:
                    server.stop()
                    os.unlink(temp_rom_path)
                    cleanup_test_logs(test_log_dir)


@pytest.mark.integration
class TestGBAServerActionParsingIntegration:
    """Test action parsing integration with game execution"""
    
    @pytest.fixture
    def server_for_parsing(self):
        """Server for testing action parsing"""
        test_log_dir = Path("logs/test/parsing_integration") / f"test_{int(time.time() * 1000)}"
        server = GBAGameServer(port=0, log_dir=test_log_dir)
        yield server
        cleanup_test_logs(test_log_dir)
    
    def test_complex_action_parsing_integration(self, server_for_parsing):
        """Test complex action combinations are parsed and executed correctly"""
        # Test individual button parsing
        result = server_for_parsing._parse_action("A")
        expected = {
            'A': True, 'B': False, 'START': False, 'SELECT': False,
            'UP': False, 'DOWN': False, 'LEFT': False, 'RIGHT': False
        }
        assert result == expected
        
        # Test combination parsing
        result = server_for_parsing._parse_action("A,B,UP")
        expected = {
            'A': True, 'B': True, 'START': False, 'SELECT': False,
            'UP': True, 'DOWN': False, 'LEFT': False, 'RIGHT': False
        }
        assert result == expected
        
        # Test case insensitive parsing
        result = server_for_parsing._parse_action("a,b,start")
        expected = {
            'A': True, 'B': True, 'START': True, 'SELECT': False,
            'UP': False, 'DOWN': False, 'LEFT': False, 'RIGHT': False
        }
        assert result == expected
        
        # Test invalid button handling
        result = server_for_parsing._parse_action("A,INVALID,B")
        expected = {
            'A': True, 'B': True, 'START': False, 'SELECT': False,
            'UP': False, 'DOWN': False, 'LEFT': False, 'RIGHT': False
        }
        assert result == expected  # Invalid buttons should be ignored
    
    def test_action_execution_without_server(self):
        """Test action execution when server not started"""
        server = GBAGameServer(port=0)
        result = server._execute_actions(["A"])
        assert result == {"error": "Game not loaded"}


@pytest.mark.integration  
class TestGBAServerMainFunctionIntegration:
    """Test main function integration with server components"""
    
    def test_main_function_integration_with_mocks(self):
        """Test main function integrates with server correctly"""
        from main import run_gba_server
        
        test_log_dir = Path("logs/test/main_integration") / f"test_{int(time.time() * 1000)}"
        
        args = Mock()
        args.game = "test_game"  
        args.server_port = 0  # Use 0 to get free port instead of fixed port
        
        # Mock ROM file existence
        with patch('os.path.exists', return_value=True):
            # Mock GBA interface
            with patch('src.emulators.gba.game_server.GBAInterface') as mock_interface_class:
                mock_interface = Mock()
                mock_interface.load_game.return_value = True
                mock_interface.get_observation.return_value = {
                    'screen': Image.new('RGB', (160, 144), 'red')
                }
                mock_interface_class.return_value = mock_interface
                
                # Mock find_free_port to return a specific port
                with patch('main.find_free_port', return_value=8080):
                    # Don't mock the server components - let real HTTP server run briefly
                    with patch('builtins.print') as mock_print:
                        # Run briefly then stop (avoid infinite loop)
                        import threading
                        
                        server_instance = None
                        
                        def run_briefly():
                            nonlocal server_instance
                            try:
                                # This will create and start a real server
                                server_instance = run_gba_server(args, test_log_dir)
                            except KeyboardInterrupt:
                                pass
                        
                        thread = threading.Thread(target=run_briefly, daemon=True)
                        thread.start()
                        
                        # Wait a moment for startup
                        time.sleep(0.5)
                        
                        # Stop the server if it was created
                        if server_instance and hasattr(server_instance, 'stop'):
                            server_instance.stop()
                        
                        # Verify integration - check the actual print format from main.py
                        mock_print.assert_any_call("Starting GBA server on port 8080")
                        mock_print.assert_any_call("Using ROM: roms/test_game.gba")
        
        cleanup_test_logs(test_log_dir) 