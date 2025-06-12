#!/usr/bin/env python3
"""
Unit and integration tests for GBA Game Server functionality.

Tests cover:
- Server startup/shutdown
- API endpoints
- Action execution
- Screenshot handling
- Error handling
- Integration with client
"""

import pytest
import asyncio
import json
import time
import base64
import threading
from unittest.mock import Mock, patch, MagicMock, call
from io import BytesIO
from PIL import Image
import requests
import unittest
import tempfile
import shutil
from pathlib import Path
import sys
import os
import socket

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.emulators.gba.game_server import GBAGameServer


def find_free_port():
    """Find a free port on localhost"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


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


class TestGBAGameServer(unittest.TestCase):
    """Unit tests for GBAGameServer class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        # Use test-specific log directory to avoid interfering with real logs
        test_log_dir = Path("logs/test/gba_test") / f"test_{int(time.time() * 1000)}"
        self.server = GBAGameServer(port=8081, log_dir=test_log_dir, game_name="gba_test")
        
    def tearDown(self):
        """Clean up test fixtures"""
        if self.server.is_running:
            self.server.stop()
        # Clean up test-specific logs - safe to delete since they're in logs/test/
        cleanup_test_logs(self.server.log_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_server_initialization(self):
        """Test server initialization"""
        assert self.server.port == 8081
        assert not self.server.is_running
        assert self.server.game_interface is None
        assert self.server.screenshot_history == []
        assert self.server.step_count == 0
        assert self.server.game_state == "waiting"
        assert self.server.max_screenshot_history == 50
    
    @patch('src.emulators.gba.game_server.GBAInterface')
    def test_server_start_success(self, mock_gba_interface):
        """Test successful server startup"""
        # Mock GBA interface
        mock_interface = Mock()
        mock_interface.load_game.return_value = True
        mock_interface.get_observation.return_value = {
            'screen': Image.new('RGB', (160, 144), color='red')
        }
        mock_gba_interface.return_value = mock_interface
        
        # Start server
        url = self.server.start("test_rom.gba")
        
        assert self.server.is_running
        assert url == "http://localhost:8081"
        assert self.server.game_state == "ready"
        assert len(self.server.screenshot_history) == 1
        
        # Cleanup
        self.server.stop()
    
    @patch('src.emulators.gba.game_server.GBAInterface')
    def test_server_start_failure(self, mock_gba_interface):
        """Test server startup failure when ROM loading fails"""
        # Mock GBA interface to fail loading
        mock_interface = Mock()
        mock_interface.load_game.return_value = False
        mock_gba_interface.return_value = mock_interface
        
        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Failed to load ROM"):
            self.server.start("invalid_rom.gba")
    
    @patch('src.emulators.gba.game_server.GBAInterface')
    def test_server_start_already_running(self, mock_gba_interface):
        """Test starting server when already running"""
        # Mock GBA interface
        mock_interface = Mock()
        mock_interface.load_game.return_value = True
        mock_interface.get_observation.return_value = {
            'screen': Image.new('RGB', (160, 144), color='red')
        }
        mock_gba_interface.return_value = mock_interface
        
        # Start server first time
        url1 = self.server.start("test_rom.gba")
        
        # Try to start again
        url2 = self.server.start("test_rom.gba")
        
        assert url1 == url2
        assert self.server.is_running
        
        # Cleanup
        self.server.stop()
    
    def test_server_stop_not_running(self):
        """Test stopping server when not running"""
        # Should not raise any errors
        self.server.stop()
        assert not self.server.is_running
    
    def test_parse_action_single_button(self):
        """Test parsing single button action"""
        result = self.server._parse_action("A")
        expected = {
            'A': True, 'B': False, 'START': False, 'SELECT': False,
            'UP': False, 'DOWN': False, 'LEFT': False, 'RIGHT': False
        }
        assert result == expected
    
    def test_parse_action_multiple_buttons(self):
        """Test parsing multiple button action"""
        result = self.server._parse_action("A,DOWN")
        expected = {
            'A': True, 'B': False, 'START': False, 'SELECT': False,
            'UP': False, 'DOWN': True, 'LEFT': False, 'RIGHT': False
        }
        assert result == expected
    
    def test_parse_action_empty(self):
        """Test parsing empty action"""
        result = self.server._parse_action("")
        expected = {
            'A': False, 'B': False, 'START': False, 'SELECT': False,
            'UP': False, 'DOWN': False, 'LEFT': False, 'RIGHT': False
        }
        assert result == expected
    
    def test_parse_action_invalid_button(self):
        """Test parsing action with invalid button"""
        result = self.server._parse_action("A,INVALID,B")
        expected = {
            'A': True, 'B': True, 'START': False, 'SELECT': False,
            'UP': False, 'DOWN': False, 'LEFT': False, 'RIGHT': False
        }
        assert result == expected
    
    def test_parse_action_case_insensitive(self):
        """Test parsing action is case insensitive"""
        result = self.server._parse_action("a,down")
        expected = {
            'A': True, 'B': False, 'START': False, 'SELECT': False,
            'UP': False, 'DOWN': True, 'LEFT': False, 'RIGHT': False
        }
        assert result == expected
    
    def test_parse_action_with_spaces(self):
        """Test parsing action with spaces"""
        result = self.server._parse_action(" A , DOWN ")
        expected = {
            'A': True, 'B': False, 'START': False, 'SELECT': False,
            'UP': False, 'DOWN': True, 'LEFT': False, 'RIGHT': False
        }
        assert result == expected
    
    @patch('src.emulators.gba.game_server.GBAInterface')
    def test_execute_actions_success(self, mock_gba_interface):
        """Test successful action execution"""
        # Setup mock interface
        mock_interface = Mock()
        mock_interface.load_game.return_value = True
        mock_interface.get_observation.return_value = {
            'screen': Image.new('RGB', (160, 144), color='blue')
        }
        mock_interface.step.return_value = (None, None, None, None)
        mock_gba_interface.return_value = mock_interface
        
        # Start server
        self.server.start("test_rom.gba")
        
        # Execute actions
        result = self.server._execute_actions(["A", "DOWN"])
        
        assert result["success"] is True
        assert result["total_actions"] == 2
        assert len(result["results"]) == 2
        assert all(r["success"] for r in result["results"])
        assert self.server.step_count == 2
        assert self.server.game_state == "playing"
        
        # Cleanup
        self.server.stop()
    
    @patch('src.emulators.gba.game_server.GBAInterface')
    def test_execute_actions_partial_failure(self, mock_gba_interface):
        """Test action execution with some actions failing"""
        # Setup mock interface
        mock_interface = Mock()
        mock_interface.load_game.return_value = True
        mock_interface.get_observation.return_value = {
            'screen': Image.new('RGB', (160, 144), color='blue')
        }
        # Make second action fail
        mock_interface.step.side_effect = [
            (None, None, None, None),  # First action succeeds
            Exception("Step failed"),   # Second action fails
            (None, None, None, None)    # Third action succeeds
        ]
        mock_gba_interface.return_value = mock_interface
        
        # Start server
        self.server.start("test_rom.gba")
        
        # Execute actions
        result = self.server._execute_actions(["A", "DOWN", "B"])
        
        assert result["success"] is True  # Overall success even with partial failure
        assert result["total_actions"] == 3
        assert len(result["results"]) == 3
        assert result["results"][0]["success"] is True
        assert result["results"][1]["success"] is False
        assert result["results"][2]["success"] is True
        assert "error" in result["results"][1]
        
        # Cleanup
        self.server.stop()
    
    def test_execute_actions_no_game(self):
        """Test action execution without loaded game"""
        result = self.server._execute_actions(["A"])
        assert result == {"error": "Game not loaded"}
    
    @patch('src.emulators.gba.game_server.GBAInterface')
    def test_screenshot_history_limit(self, mock_gba_interface):
        """Test screenshot history respects max limit and saves to log directory"""
        # Setup mock interface
        mock_interface = Mock()
        mock_interface.load_game.return_value = True
        mock_interface.get_observation.return_value = {
            'screen': Image.new('RGB', (160, 144), color='green')
        }
        mock_interface.step.return_value = (None, None, None, None)
        mock_gba_interface.return_value = mock_interface
        
        # Set a small limit for testing
        self.server.max_screenshot_history = 3
        
        # Start server
        self.server.start("test_rom.gba")
        
        # Execute multiple actions to generate screenshots
        for i in range(5):
            self.server._execute_actions(["A"])
        
        # Should only keep the last 3 screenshots in memory
        assert len(self.server.screenshot_history) == 3
        
        # Verify screenshots are saved to the correct directory structure
        screenshot_dir = self.server.screenshot_dir
        assert screenshot_dir.exists()
        assert screenshot_dir.name == "game_screen"
        
        # Verify the log directory structure is in test directory
        log_dir_str = str(self.server.log_dir)
        assert "logs/test" in log_dir_str
        assert "gba_test" in log_dir_str
        
        # Verify log file exists
        log_file = self.server.log_dir / "agent_session.log"
        assert log_file.exists()
        
        # Verify some screenshot files were actually created
        screenshot_files = list(screenshot_dir.glob("screenshot_*.png"))
        assert len(screenshot_files) > 0
        
        # Cleanup
        self.server.stop()


class TestGBAGameServerIntegration:
    """Integration tests for GBA Game Server with HTTP API"""
    
    @pytest.fixture(scope="class")
    def server_url(self):
        """Start a test server for integration tests"""
        # Find a free port dynamically
        free_port = find_free_port()
        # Use test-specific log directory
        test_log_dir = Path("logs/test/gba_integration") / f"test_{int(time.time() * 1000)}"
        server = GBAGameServer(port=free_port, log_dir=test_log_dir, game_name="gba_test")
        
        # Mock the GBA interface for testing
        with patch('src.emulators.gba.game_server.GBAInterface') as mock_gba:
            mock_interface = Mock()
            mock_interface.load_game.return_value = True
            mock_interface.get_observation.return_value = {
                'screen': Image.new('RGB', (160, 144), color='green')
            }
            mock_interface.step.return_value = (None, None, None, None)
            mock_gba.return_value = mock_interface
            
            # Start server
            url = server.start("test_rom.gba")
            
            # Wait for server to be ready
            time.sleep(0.5)
            
            yield url
            
            # Cleanup - safe to remove test logs
            server.stop()
            cleanup_test_logs(server.log_dir)
    
    def test_health_endpoint(self, server_url):
        """Test health check endpoint"""
        response = requests.get(f"{server_url}/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["server"] == "gba_game_server"
    
    def test_status_endpoint(self, server_url):
        """Test status endpoint"""
        response = requests.get(f"{server_url}/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "state" in data
        assert "step" in data
        assert "running" in data
        assert "screenshot_history_count" in data
        assert data["running"] is True
    
    def test_screenshots_endpoint(self, server_url):
        """Test screenshots endpoint"""
        response = requests.get(f"{server_url}/screenshots?count=1")
        assert response.status_code == 200
        
        data = response.json()
        assert "screenshots" in data
        assert "count" in data
        assert "format" in data
        assert data["format"] == "base64_png"
        assert len(data["screenshots"]) >= 1
        
        # Verify screenshot structure
        screenshot = data["screenshots"][0]
        assert "step" in screenshot
        assert "screenshot" in screenshot
        assert "timestamp" in screenshot
        
        # Verify base64 image can be decoded
        image_data = base64.b64decode(screenshot["screenshot"])
        img = Image.open(BytesIO(image_data))
        assert img.size == (160, 144)
    
    def test_screenshots_endpoint_multiple(self, server_url):
        """Test screenshots endpoint with multiple screenshots"""
        # First execute some actions to generate more screenshots
        payload = {"actions": ["A", "B", "START"]}
        requests.post(f"{server_url}/actions", json=payload)
        
        # Now request multiple screenshots
        response = requests.get(f"{server_url}/screenshots?count=3")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["screenshots"]) >= 1  # Should have at least initial screenshot
        assert data["count"] >= 1
    
    def test_screenshots_endpoint_invalid_count(self, server_url):
        """Test screenshots endpoint with invalid count parameter"""
        # Test with invalid count (should default to 1)
        response = requests.get(f"{server_url}/screenshots?count=invalid")
        assert response.status_code == 200
        
        data = response.json()
        assert data["count"] >= 1
        
        # Test with count > 20 (should be limited to 20)
        response = requests.get(f"{server_url}/screenshots?count=50")
        assert response.status_code == 200
        
        data = response.json()
        assert data["count"] <= 20
    
    def test_screenshots_endpoint_no_count(self, server_url):
        """Test screenshots endpoint without count parameter"""
        response = requests.get(f"{server_url}/screenshots")
        assert response.status_code == 200
        
        data = response.json()
        assert data["count"] >= 1  # Should default to 1
    
    def test_actions_endpoint(self, server_url):
        """Test actions endpoint"""
        payload = {"actions": ["A", "DOWN", "A"]}
        response = requests.post(f"{server_url}/actions", 
                               json=payload,
                               headers={'Content-Type': 'application/json'})
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["total_actions"] == 3
        assert len(data["results"]) == 3
        assert all(r["success"] for r in data["results"])
    
    def test_actions_endpoint_empty_list(self, server_url):
        """Test actions endpoint with empty actions list"""
        payload = {"actions": []}
        response = requests.post(f"{server_url}/actions", 
                               json=payload,
                               headers={'Content-Type': 'application/json'})
        assert response.status_code == 200
        
        data = response.json()
        assert "error" in data
        assert data["error"] == "Empty actions list"
    
    def test_actions_endpoint_invalid_format(self, server_url):
        """Test actions endpoint with invalid format"""
        payload = {"actions": "not_a_list"}
        response = requests.post(f"{server_url}/actions", 
                               json=payload,
                               headers={'Content-Type': 'application/json'})
        assert response.status_code == 200
        
        data = response.json()
        assert "error" in data
    
    def test_actions_endpoint_missing_actions(self, server_url):
        """Test actions endpoint with missing actions field"""
        payload = {"not_actions": ["A"]}
        response = requests.post(f"{server_url}/actions", 
                               json=payload,
                               headers={'Content-Type': 'application/json'})
        assert response.status_code == 200
        
        data = response.json()
        assert "error" in data
        assert data["error"] == "Empty actions list"
    
    def test_actions_endpoint_invalid_json(self, server_url):
        """Test actions endpoint with invalid JSON"""
        response = requests.post(f"{server_url}/actions", 
                               data="invalid json",
                               headers={'Content-Type': 'application/json'})
        assert response.status_code == 200
        
        data = response.json()
        assert "error" in data
    
    def test_reset_endpoint(self, server_url):
        """Test reset endpoint"""
        response = requests.post(f"{server_url}/reset")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Game reset"
    
    def test_invalid_endpoint(self, server_url):
        """Test invalid endpoint returns 404"""
        response = requests.get(f"{server_url}/invalid")
        assert response.status_code == 404
    
    def test_cors_headers(self, server_url):
        """Test CORS headers are present"""
        response = requests.get(f"{server_url}/health")
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers
        assert response.headers["Access-Control-Allow-Origin"] == "*"


class TestGBAClientIntegration:
    """Integration tests for GBA client with real server"""
    
    def test_client_import(self):
        """Test that client example can be imported"""
        try:
            from examples.gba_client_example import GBAGameClient, call_llm_for_actions
            assert GBAGameClient is not None
            assert call_llm_for_actions is not None
        except ImportError as e:
            pytest.fail(f"Failed to import client example: {e}")
    
    def test_client_initialization(self):
        """Test client initialization"""
        from examples.gba_client_example import GBAGameClient
        
        # Test default URL
        client = GBAGameClient()
        assert client.server_url == "http://localhost:8080"
        assert client.step_count == 0
        
        # Test custom URL
        client = GBAGameClient("http://localhost:9000/")
        assert client.server_url == "http://localhost:9000"  # Should strip trailing slash
    
    def test_client_with_real_server(self):
        """Test client functionality with real server"""
        import tempfile
        import os
        from examples.gba_client_example import GBAGameClient
        
        # Create a temporary ROM file
        with tempfile.NamedTemporaryFile(suffix='.gba', delete=False) as temp_rom:
            temp_rom.write(b"fake rom data for client test")
            temp_rom_path = temp_rom.name
        
        try:
            # Create a real server instance but mock the GBA interface
            with patch('src.emulators.gba.game_server.GBAInterface') as mock_gba_interface:
                # Mock the GBA interface
                mock_interface = Mock()
                mock_interface.load_game.return_value = True
                mock_interface.get_observation.return_value = {
                    'screen': Image.new('RGB', (160, 144), color='purple')
                }
                mock_interface.step.return_value = (None, None, None, None)
                mock_gba_interface.return_value = mock_interface
                
                # Find a free port dynamically
                free_port = find_free_port()
                
                # Create and start real server with test log directory
                from src.emulators.gba.game_server import GBAGameServer
                test_log_dir = Path("logs/test/gba_client") / f"test_{int(time.time() * 1000)}"
                server = GBAGameServer(port=free_port, log_dir=test_log_dir, game_name="gba_test")
                
                try:
                    # Start server
                    url = server.start(temp_rom_path)
                    time.sleep(0.5)  # Wait for server to be ready
                    
                    # Create client pointing to our test server
                    client = GBAGameClient(f"http://localhost:{free_port}")
                    
                    # Test health check
                    assert client.health_check() is True
                    
                    # Test get status
                    status = client.get_status()
                    assert "state" in status
                    assert "step" in status
                    assert "running" in status
                    assert status["running"] is True
                    
                    # Test get screenshots
                    screenshots = client.get_screenshots(count=1)
                    assert len(screenshots) >= 1
                    assert "image" in screenshots[0]
                    assert "step" in screenshots[0]
                    assert isinstance(screenshots[0]["image"], Image.Image)
                    
                    # Test send actions
                    result = client.send_actions(["A", "B"])
                    assert result["success"] is True
                    assert result["total_actions"] == 2
                    
                    # Test reset game
                    reset_result = client.reset_game()
                    assert reset_result["success"] is True
                    assert reset_result["message"] == "Game reset"
                    
                    print(f"✅ Client integration test passed on port {free_port}!")
                    
                finally:
                    # Stop the server
                    if server.is_running:
                        server.stop()
                    # Clean up the test log directory - safe to delete
                    cleanup_test_logs(server.log_dir)
        
        finally:
            # Clean up temp ROM file
            if os.path.exists(temp_rom_path):
                os.unlink(temp_rom_path)

    def test_mock_llm_actions(self):
        """Test mock LLM action generation"""
        from examples.gba_client_example import call_llm_for_actions
        
        # Create mock screenshots
        screenshots = [
            {'image': Image.new('RGB', (160, 144)), 'step': 1, 'timestamp': time.time()},
            {'image': Image.new('RGB', (160, 144)), 'step': 2, 'timestamp': time.time()}
        ]
        
        # Test mock action generation (when litellm not available)
        actions = call_llm_for_actions(screenshots, 0)
        assert isinstance(actions, list)
        assert len(actions) >= 1  # Should return at least 1 action
        assert all(isinstance(action, str) for action in actions)
        
        # If litellm is available but call fails, it returns 1 action
        # If litellm is not available, it returns 3 mock actions
        assert len(actions) in [1, 3]
    
    def test_mock_llm_actions_empty_screenshots(self):
        """Test mock LLM action generation with empty screenshots"""
        from examples.gba_client_example import call_llm_for_actions
        
        # Test with empty screenshots
        actions = call_llm_for_actions([], 0)
        assert isinstance(actions, list)
        assert len(actions) >= 1


def test_server_mode_main_function():
    """Test the main server mode function with real server but mocked GBA interface"""
    from main import run_gba_server
    import tempfile
    import os
    import threading
    import time
    
    # Create a temporary ROM file
    with tempfile.NamedTemporaryFile(suffix='.gba', delete=False) as temp_rom:
        temp_rom.write(b"fake rom data for main test")
        temp_rom_path = temp_rom.name
    
    try:
        # Mock args with a free port
        free_port = find_free_port()
        args = Mock()
        args.game = "pokemon_red"
        args.server_port = free_port
        
        # Create test-specific log directory
        test_log_dir = Path("logs/test/main_function") / f"test_{int(time.time() * 1000)}"
        
        # Mock ROM file existence to return True for the expected path but don't actually copy files
        def mock_exists(path):
            if path == "roms/pokemon_red.gba":
                return True
            return False
        
        with patch('os.path.exists', side_effect=mock_exists):
            # Mock only the GBA interface, not the entire server
            with patch('src.emulators.gba.game_server.GBAInterface') as mock_gba_interface:
                mock_interface = Mock()
                mock_interface.load_game.return_value = True
                mock_interface.get_observation.return_value = {
                    'screen': Image.new('RGB', (160, 144), color='red')
                }
                mock_gba_interface.return_value = mock_interface
                
                # Mock the GBAGameServer.start method to avoid loading real ROM
                def mock_server_start(rom_path):
                    # Just return success without actually loading ROM
                    return f"http://localhost:{free_port}"
                
                with patch('src.emulators.gba.game_server.GBAGameServer.start', side_effect=mock_server_start):
                    # Mock print to capture output
                    with patch('builtins.print') as mock_print:
                        # Run in a separate thread since run_gba_server has a while loop
                        server_thread = threading.Thread(target=run_gba_server, args=(args, test_log_dir))
                        server_thread.daemon = True
                        server_thread.start()
                        
                        # Wait for server to start
                        time.sleep(1.0)
                        
                        # Verify the output messages were printed
                        mock_print.assert_any_call(f"Starting GBA server on port {free_port}")
                        mock_print.assert_any_call("Using ROM: roms/pokemon_red.gba")
                        
                        print(f"✅ Main function test passed on port {free_port}!")
    
    finally:
        # Clean up temp ROM file - DO NOT touch production ROM files
        if os.path.exists(temp_rom_path):
            os.unlink(temp_rom_path)
        
        # Clean up test logs - safe to delete since they're in logs/test/
        cleanup_test_logs(test_log_dir)

def test_server_http_endpoints():
    """Test server HTTP endpoints with real server instance"""
    import tempfile
    import os
    
    # Create a temporary ROM file
    with tempfile.NamedTemporaryFile(suffix='.gba', delete=False) as temp_rom:
        temp_rom.write(b"fake rom data")
        temp_rom_path = temp_rom.name
    
    try:
        # Create a real server instance but mock the GBA interface
        with patch('src.emulators.gba.game_server.GBAInterface') as mock_gba_interface:
            # Mock the GBA interface
            mock_interface = Mock()
            mock_interface.load_game.return_value = True
            mock_interface.get_observation.return_value = {
                'screen': Image.new('RGB', (160, 144), color='blue')
            }
            mock_gba_interface.return_value = mock_interface
            
            # Find a free port dynamically
            free_port = find_free_port()
            
            # Import and create real server with test log directory
            from src.emulators.gba.game_server import GBAGameServer
            test_log_dir = Path("logs/test/gba_http") / f"test_{int(time.time() * 1000)}"
            server = GBAGameServer(port=free_port, log_dir=test_log_dir, game_name="gba_test")
            
            try:
                # Start server with temp ROM file
                url = server.start(temp_rom_path)
                assert url == f"http://localhost:{free_port}"
                assert server.is_running is True
                
                # Wait a moment for server to be ready
                time.sleep(0.5)
                
                # Test that the server is actually running
                import requests
                response = requests.get(f"http://localhost:{free_port}/health", timeout=2)
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "healthy"
                assert data["server"] == "gba_game_server"
                
                # Test status endpoint
                response = requests.get(f"http://localhost:{free_port}/status", timeout=2)
                assert response.status_code == 200
                status_data = response.json()
                assert "state" in status_data
                assert "running" in status_data
                assert status_data["running"] is True
                
                print(f"✅ HTTP endpoints test passed on port {free_port}!")
                
            finally:
                # Stop the server
                if server.is_running:
                    server.stop()
                # Clean up the test log directory - safe to delete
                cleanup_test_logs(server.log_dir)
    
    finally:
        # Clean up temp ROM file
        if os.path.exists(temp_rom_path):
            os.unlink(temp_rom_path)

def test_server_mode_main_function_rom_not_found():
    """Test the main server mode function when ROM file not found"""
    from main import run_gba_server
    
    # Mock args
    args = Mock()
    args.game = "nonexistent_game"
    args.server_port = 8084
    
    # Mock ROM file not existing for all extensions
    with patch('os.path.exists', return_value=False):
        # Mock sys.exit to raise SystemExit (which is what it normally does)
        with patch('sys.exit', side_effect=SystemExit(1)) as mock_exit:
            # Mock print to capture output
            with patch('builtins.print') as mock_print:
                # Should raise SystemExit
                with pytest.raises(SystemExit) as exc_info:
                    run_gba_server(args)
                
                # Verify exit code
                assert exc_info.value.code == 1
                
                # Verify the error message was printed
                expected_message = "ROM file not found. Tried: roms/nonexistent_game.gba, roms/nonexistent_game.gb, roms/nonexistent_game.gbc"
                mock_print.assert_any_call(expected_message)
                # Verify sys.exit was called with code 1
                mock_exit.assert_called_once_with(1)

def test_server_mode_main_function_gb_file():
    """Test the main server mode function with .gb file"""
    from main import run_gba_server
    import tempfile
    import os
    import threading
    import time
    
    # Create a temporary ROM file with .gb extension
    with tempfile.NamedTemporaryFile(suffix='.gb', delete=False) as temp_rom:
        temp_rom.write(b"fake gb rom data")
        temp_rom_path = temp_rom.name
    
    try:
        # Mock args with a free port
        free_port = find_free_port()
        args = Mock()
        args.game = "pokemon_red"
        args.server_port = free_port
        
        # Create test-specific log directory
        test_log_dir = Path("logs/test/main_function_gb") / f"test_{int(time.time() * 1000)}"
        
        # Mock ROM file existence - .gba doesn't exist but .gb does
        def mock_exists(path):
            if path == "roms/pokemon_red.gb":
                return True
            return False
        
        with patch('os.path.exists', side_effect=mock_exists):
            # Mock only the GBA interface, not the entire server
            with patch('src.emulators.gba.game_server.GBAInterface') as mock_gba_interface:
                mock_interface = Mock()
                mock_interface.load_game.return_value = True
                mock_interface.get_observation.return_value = {
                    'screen': Image.new('RGB', (160, 144), color='green')
                }
                mock_gba_interface.return_value = mock_interface
                
                # Mock the GBAGameServer.start method to avoid loading real ROM
                def mock_server_start(rom_path):
                    # Just return success without actually loading ROM
                    return f"http://localhost:{free_port}"
                
                with patch('src.emulators.gba.game_server.GBAGameServer.start', side_effect=mock_server_start):
                    # Mock print to capture output
                    with patch('builtins.print') as mock_print:
                        # Run in a separate thread since run_gba_server has a while loop
                        server_thread = threading.Thread(target=run_gba_server, args=(args, test_log_dir))
                        server_thread.daemon = True
                        server_thread.start()
                        
                        # Wait for server to start
                        time.sleep(1.0)
                        
                        # Verify the output messages were printed
                        mock_print.assert_any_call(f"Starting GBA server on port {free_port}")
                        mock_print.assert_any_call("Using ROM: roms/pokemon_red.gb")
                        
                        print(f"✅ GB file test passed on port {free_port}!")
    
    finally:
        # Clean up temp ROM file - DO NOT touch production ROM files
        if os.path.exists(temp_rom_path):
            os.unlink(temp_rom_path)
        
        # Clean up test logs - safe to delete since they're in logs/test/
        cleanup_test_logs(test_log_dir)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"]) 