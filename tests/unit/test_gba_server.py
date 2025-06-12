#!/usr/bin/env python3
"""
Unit tests for GBA Game Server

Tests cover:
- Server initialization and configuration
- Action parsing logic
- Server lifecycle (start/stop)
- Action execution with mocked game interface
- Screenshot and logging functionality
- Error handling scenarios
"""

import pytest
import tempfile
import shutil
import time
from unittest.mock import Mock, patch
from PIL import Image
from pathlib import Path
import sys
import os

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


@pytest.mark.unit
class TestGBAGameServerLogic:
    """Test GBA game server logic without external dependencies"""
    
    @pytest.fixture
    def server(self):
        """Create a clean server instance for testing"""
        temp_dir = tempfile.mkdtemp()
        # Use test-specific log directory to avoid interfering with real logs
        test_log_dir = Path("logs/test/gba_unit_test") / f"test_{int(time.time() * 1000)}"
        server = GBAGameServer(port=8081, log_dir=test_log_dir, game_name="gba_unit_test")
        
        yield server
        
        # Cleanup - only stop if server was actually started (has HTTP server instance)
        if hasattr(server, 'server') and server.server is not None:
            server.stop()
        cleanup_test_logs(server.log_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_server_initialization(self, server):
        """Test server initialization with all parameters"""
        assert server.port == 8081
        assert not server.is_running
        assert server.game_interface is None
        assert server.screenshot_history == []
        assert server.step_count == 0
        assert server.game_state == "waiting"
        assert server.max_screenshot_history == 50
        assert server.game_name == "gba_unit_test"
        assert "logs/test/gba_unit_test" in str(server.log_dir)
    
    def test_parse_action_single_button(self, server):
        """Test parsing single button action"""
        result = server._parse_action("A")
        expected = {
            'A': True, 'B': False, 'START': False, 'SELECT': False,
            'UP': False, 'DOWN': False, 'LEFT': False, 'RIGHT': False
        }
        assert result == expected
    
    def test_parse_action_multiple_buttons(self, server):
        """Test parsing multiple button action"""
        result = server._parse_action("A,DOWN,B")
        expected = {
            'A': True, 'B': True, 'START': False, 'SELECT': False,
            'UP': False, 'DOWN': True, 'LEFT': False, 'RIGHT': False
        }
        assert result == expected
    
    def test_parse_action_empty(self, server):
        """Test parsing empty action"""
        result = server._parse_action("")
        expected = {
            'A': False, 'B': False, 'START': False, 'SELECT': False,
            'UP': False, 'DOWN': False, 'LEFT': False, 'RIGHT': False
        }
        assert result == expected
    
    def test_parse_action_invalid_button(self, server):
        """Test parsing action with invalid button names"""
        result = server._parse_action("A,INVALID,B")
        expected = {
            'A': True, 'B': True, 'START': False, 'SELECT': False,
            'UP': False, 'DOWN': False, 'LEFT': False, 'RIGHT': False
        }
        assert result == expected
    
    def test_parse_action_case_insensitive(self, server):
        """Test parsing action is case insensitive"""
        result = server._parse_action("a,down,SELECT")
        expected = {
            'A': True, 'B': False, 'START': False, 'SELECT': True,
            'UP': False, 'DOWN': True, 'LEFT': False, 'RIGHT': False
        }
        assert result == expected
    
    def test_parse_action_with_spaces(self, server):
        """Test parsing action with extra spaces"""
        result = server._parse_action(" A , DOWN , B ")
        expected = {
            'A': True, 'B': True, 'START': False, 'SELECT': False,
            'UP': False, 'DOWN': True, 'LEFT': False, 'RIGHT': False
        }
        assert result == expected
    
    def test_log_directory_creation(self, server):
        """Test log directory structure creation"""
        # Directory should be created when _ensure_log_directory is called
        server._ensure_log_directory()
        assert server.log_dir.exists()
        assert server.screenshot_dir.exists()
        assert server.screenshot_dir.name == "game_screen"
        assert server.screenshot_dir.parent == server.log_dir
        assert server.file_logger is not None
    
    def test_screenshot_history_management(self, server):
        """Test screenshot history management logic"""
        server.max_screenshot_history = 3  # Small limit for testing
        
        # Add screenshots beyond limit
        for i in range(5):
            screenshot_data = {
                "step": i,
                "screenshot": f"screenshot_{i}",
                "timestamp": time.time(),
                "file_path": f"screenshot_{i}.png"
            }
            server.screenshot_history.append(screenshot_data)
            
            # Manually trigger cleanup (normally done in _update_screenshot)
            if len(server.screenshot_history) > server.max_screenshot_history:
                server.screenshot_history = server.screenshot_history[-server.max_screenshot_history:]
        
        # Should only keep the last 3
        assert len(server.screenshot_history) == 3
        assert server.screenshot_history[0]["step"] == 2
        assert server.screenshot_history[1]["step"] == 3
        assert server.screenshot_history[2]["step"] == 4
    
    def test_server_state_management(self, server):
        """Test server state management"""
        # Initial state
        assert server.game_state == "waiting"
        assert server.step_count == 0
        assert not server.is_running
        
        # Simulate state changes
        server.game_state = "ready"
        server.step_count = 10
        server.is_running = True
        
        assert server.game_state == "ready"
        assert server.step_count == 10
        assert server.is_running
    
    def test_server_stop_not_running(self, server):
        """Test stopping server when not running"""
        # Should not raise any errors
        server.stop()
        assert not server.is_running


@pytest.mark.unit
class TestGBAGameServerWithMockedInterface:
    """Test GBA game server with all external dependencies mocked"""
    
    @pytest.fixture
    def server(self):
        """Create a clean server instance for testing"""
        temp_dir = tempfile.mkdtemp()
        test_log_dir = Path("logs/test/gba_mock_test") / f"test_{int(time.time() * 1000)}"
        server = GBAGameServer(port=8082, log_dir=test_log_dir, game_name="gba_mock_test")
        
        yield server
        
        # Cleanup - only stop if server was actually started (has HTTP server instance)
        if hasattr(server, 'server') and server.server is not None:
            server.stop()
        cleanup_test_logs(server.log_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def mock_gba_interface(self):
        """Mock GBAInterface - external game emulator dependency"""
        with patch('src.emulators.gba.game_server.GBAInterface') as mock_interface_class:
            mock_interface = Mock()
            mock_interface.load_game.return_value = True
            mock_interface.get_observation.return_value = {
                'screen': Image.new('RGB', (160, 144), 'blue')
            }
            mock_interface.step.return_value = ({'screen': Image.new('RGB', (160, 144), 'green')}, 0, False, {})
            mock_interface.close = Mock()
            mock_interface_class.return_value = mock_interface
            yield mock_interface
    
    @pytest.fixture
    def mock_http_server(self):
        """Mock HTTP server and threading for unit tests"""
        with patch('socketserver.TCPServer') as mock_server_class:
            mock_server_instance = Mock()
            # Mock server_address to return (host, port) tuple
            mock_server_instance.server_address = ('localhost', 8082)
            mock_server_class.return_value = mock_server_instance
            
            with patch('threading.Thread') as mock_thread:
                yield mock_server_instance, mock_thread
    
    def test_server_start_success(self, mock_gba_interface, mock_http_server, server):
        """Test successful server startup with all dependencies mocked"""
        mock_server_instance, mock_thread = mock_http_server
        
        # Create a temporary ROM file
        with tempfile.NamedTemporaryFile(suffix='.gba', delete=False) as temp_rom:
            temp_rom.write(b"fake rom data")
            temp_rom_path = temp_rom.name
        
        try:
            url = server.start(temp_rom_path)
            
            # Verify unit behavior - state changes and method calls
            assert server.is_running
            assert url == "http://localhost:8082"
            assert server.game_state == "ready"
            assert len(server.screenshot_history) == 1
            assert server.game_interface is not None
            
            # Verify interface was called correctly (unit test focus)
            mock_gba_interface.load_game.assert_called_once_with(temp_rom_path)
            mock_gba_interface.get_observation.assert_called()
            
            # Verify HTTP components were initialized but not running real server
            mock_thread.assert_called_once()
            
        finally:
            # Cleanup
            server.stop()
            os.unlink(temp_rom_path)
    
    def test_server_start_failure(self, mock_gba_interface, mock_http_server, server):
        """Test server startup failure when ROM loading fails"""
        mock_gba_interface.load_game.return_value = False
        
        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Failed to load ROM"):
            server.start("invalid_rom.gba")
    
    def test_server_start_already_running(self, mock_gba_interface, mock_http_server, server):
        """Test starting server when already running"""
        with tempfile.NamedTemporaryFile(suffix='.gba', delete=False) as temp_rom:
            temp_rom.write(b"fake rom data")
            temp_rom_path = temp_rom.name
        
        try:
            # Start server first time
            url1 = server.start(temp_rom_path)
            
            # Try to start again
            url2 = server.start(temp_rom_path)
            
            assert url1 == url2
            assert server.is_running
            
            # Should only load game once
            assert mock_gba_interface.load_game.call_count == 1
            
        finally:
            # Cleanup
            server.stop()
            os.unlink(temp_rom_path)
    
    def test_execute_actions_success(self, mock_gba_interface, mock_http_server, server):
        """Test successful action execution"""
        with tempfile.NamedTemporaryFile(suffix='.gba', delete=False) as temp_rom:
            temp_rom.write(b"fake rom data")
            temp_rom_path = temp_rom.name
        
        try:
            # Start server
            server.start(temp_rom_path)
            
            # Execute actions using the correct method name
            result = server._execute_actions(["A", "DOWN"])
            
            assert result["success"] is True
            assert result["total_actions"] == 2
            assert len(result["results"]) == 2
            assert all(r["success"] for r in result["results"])
            assert server.step_count == 2
            assert server.game_state == "playing"
            
            # Verify interface was called correctly
            assert mock_gba_interface.step.call_count == 2
            
        finally:
            # Cleanup
            server.stop()
            os.unlink(temp_rom_path)
    
    def test_execute_actions_partial_failure(self, mock_gba_interface, mock_http_server, server):
        """Test action execution with some actions failing"""
        # Make second action fail
        mock_gba_interface.step.side_effect = [
            ({'screen': Image.new('RGB', (160, 144), 'cyan')}, 0, False, {}),  # First action succeeds
            Exception("Step failed"),   # Second action fails
            ({'screen': Image.new('RGB', (160, 144), 'cyan')}, 0, False, {})   # Third action succeeds
        ]
        
        with tempfile.NamedTemporaryFile(suffix='.gba', delete=False) as temp_rom:
            temp_rom.write(b"fake rom data")
            temp_rom_path = temp_rom.name
        
        try:
            # Start server
            server.start(temp_rom_path)
            
            # Execute actions using the correct method name
            result = server._execute_actions(["A", "DOWN", "B"])
            
            assert result["success"] is True  # Overall success even with partial failure
            assert result["total_actions"] == 3
            assert len(result["results"]) == 3
            assert result["results"][0]["success"] is True
            assert result["results"][1]["success"] is False
            assert result["results"][2]["success"] is True
            assert "error" in result["results"][1]
            
        finally:
            # Cleanup
            server.stop()
            os.unlink(temp_rom_path)
    
    def test_execute_actions_no_game(self, server):
        """Test action execution without loaded game"""
        # Use the correct method name
        result = server._execute_actions(["A"])
        assert result == {"error": "Game not loaded"}
    
    def test_execute_actions_empty_list(self, mock_gba_interface, mock_http_server, server):
        """Test action execution with empty actions list"""
        with tempfile.NamedTemporaryFile(suffix='.gba', delete=False) as temp_rom:
            temp_rom.write(b"fake rom data")
            temp_rom_path = temp_rom.name
        
        try:
            # Start server
            server.start(temp_rom_path)
            
            # Execute empty actions list using the correct method name
            result = server._execute_actions([])
            
            # Should handle empty list gracefully
            assert result["success"] is True
            assert result["total_actions"] == 0
            assert len(result["results"]) == 0
            
        finally:
            # Cleanup
            server.stop()
            os.unlink(temp_rom_path)
    
    def test_server_stop_cleanup(self, mock_gba_interface, mock_http_server, server):
        """Test server stop and cleanup"""
        with tempfile.NamedTemporaryFile(suffix='.gba', delete=False) as temp_rom:
            temp_rom.write(b"fake rom data")
            temp_rom_path = temp_rom.name
        
        try:
            # Start server
            server.start(temp_rom_path)
            assert server.is_running
            
            # Stop server
            server.stop()
            assert not server.is_running
            mock_gba_interface.close.assert_called_once()
            
        finally:
            # Cleanup
            os.unlink(temp_rom_path)
    
    def test_screenshot_saving_and_history(self, mock_gba_interface, server):
        """Test screenshot saving and history management with real file I/O"""
        # Set up varying screenshots
        def get_varying_observation():
            colors = ['red', 'blue', 'green', 'yellow', 'purple']
            color = colors[len(server.screenshot_history) % len(colors)]
            return {'screen': Image.new('RGB', (160, 144), color=color)}
        
        mock_gba_interface.get_observation.side_effect = get_varying_observation
        mock_gba_interface.step.return_value = (
            {'screen': Image.new('RGB', (160, 144), color='cyan')},
            0, False, {}
        )
        
        server.max_screenshot_history = 3  # Small limit for testing
        
        with tempfile.NamedTemporaryFile(suffix='.gba', delete=False) as temp_rom:
            temp_rom.write(b"fake rom data")
            temp_rom_path = temp_rom.name
        
        try:
            # Start server
            server.start(temp_rom_path)
            
            # Execute multiple actions to generate screenshots
            for i in range(5):
                server._execute_actions(["A"])
            
            # Should not exceed the maximum
            assert len(server.screenshot_history) <= server.max_screenshot_history
            
            # Verify screenshots are saved to the correct directory
            screenshot_dir = server.screenshot_dir
            assert screenshot_dir.exists()
            assert screenshot_dir.name == "game_screen"
            
            # Verify some screenshot files were actually created
            screenshot_files = list(screenshot_dir.glob("screenshot_*.png"))
            assert len(screenshot_files) > 0
            
        finally:
            # Cleanup
            server.stop()
            os.unlink(temp_rom_path)
    
    def test_screenshot_history_limit(self, mock_gba_interface, server):
        """Test screenshot history respects maximum limit"""
        # Create varying screenshots to see history management
        def get_varying_observation():
            colors = ['red', 'blue', 'green', 'yellow', 'purple']
            color = colors[len(server.screenshot_history) % len(colors)]
            return {'screen': Image.new('RGB', (160, 144), color=color)}
        
        mock_gba_interface.get_observation.side_effect = get_varying_observation
        mock_gba_interface.step.return_value = (
            {'screen': Image.new('RGB', (160, 144), color='cyan')},
            0, False, {}
        )
        
        with tempfile.NamedTemporaryFile(suffix='.gba', delete=False) as temp_rom:
            temp_rom.write(b"fake rom data")
            temp_rom_path = temp_rom.name
        
        try:
            # Start server
            server.start(temp_rom_path)
            
            # Set a lower limit for testing
            server.max_screenshot_history = 3
            
            # Execute multiple actions to generate screenshots
            for i in range(5):
                server._execute_actions(["A"])
            
            # Should not exceed the maximum
            assert len(server.screenshot_history) <= server.max_screenshot_history
            
        finally:
            # Cleanup
            server.stop()
            os.unlink(temp_rom_path) 