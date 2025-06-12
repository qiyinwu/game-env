import http.server
import socketserver
import json
import threading
import time
import base64
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any
from io import BytesIO
from datetime import datetime

from src.emulators.gba.interface import GBAInterface

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GBAGameServer:
    """HTTP server for GBA game control via REST API"""
    
    def __init__(self, port: int = 8080, log_dir: Optional[Path] = None, game_name: str = "unknown_game"):
        """Initialize GBA Game Server"""
        self.port = port
        self.game_name = game_name
        self.is_running = False
        self.game_interface = None
        self.server = None
        self.server_thread = None
        self.current_screenshot = None
        self.screenshot_history = []
        self.step_count = 0
        self.game_state = "waiting"
        self.max_screenshot_history = 50
        
        # Set up log directory path but don't create it yet
        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            # Use existing log structure: logs/{game_name}/gba_server/{timestamp}
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_dir = Path("logs") / game_name / "gba_server" / timestamp
        
        # Set screenshot directory path but don't create it yet
        self.screenshot_dir = self.log_dir / "game_screen"
        
        # File logger will be set up when needed
        self.file_logger = None

    def _ensure_log_directory(self):
        """Create log directory and set up logger if not already done"""
        if not self.log_dir.exists():
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"GBA Server log directory: {self.log_dir}")
            logger.info(f"Screenshots will be saved to: {self.screenshot_dir}")
        
        if self.file_logger is None:
            self.file_logger = self._setup_file_logger()

    def _setup_file_logger(self) -> logging.Logger:
        """Set up file logger using existing pattern"""
        file_logger = logging.getLogger(f"gba_server_{self.port}")
        file_logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates
        for handler in file_logger.handlers[:]:
            file_logger.removeHandler(handler)
        
        # Create file handler
        log_file = self.log_dir / "agent_session.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        file_logger.addHandler(file_handler)
        return file_logger

    def start(self, rom_path: str) -> str:
        """Start the GBA game server"""
        if self.is_running:
            logger.warning("Server is already running")
            return f"http://localhost:{self.port}"
        
        # Ensure log directory exists before starting
        self._ensure_log_directory()
            
        # Initialize GBA game
        self.game_interface = GBAInterface(render=False)
        if not self.game_interface.load_game(rom_path):
            raise RuntimeError(f"Failed to load ROM: {rom_path}")
        
        # Get initial screenshot
        self._update_screenshot()
        self.game_state = "ready"
        
        # Create and start HTTP server
        handler = self._create_request_handler()
        socketserver.TCPServer.allow_reuse_address = True
        self.server = socketserver.TCPServer(("", self.port), handler)
        self.is_running = True
        
        # Run server in background thread
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        logger.info(f"GBA Game Server started at http://localhost:{self.port}")
        return f"http://localhost:{self.port}"
        
    def stop(self) -> None:
        """Stop the server"""
        if not self.is_running:
            return
            
        if self.game_interface:
            self.game_interface.close()
            
        self.server.shutdown()
        self.server.server_close()
        self.is_running = False
        logger.info("GBA Game Server stopped")
    
    def _update_screenshot(self):
        """Update current screenshot from game"""
        if self.game_interface:
            obs = self.game_interface.get_observation()
            if obs and obs.get('screen'):
                # Ensure log directory exists before saving screenshot
                self._ensure_log_directory()
                
                # Convert PIL Image to base64
                buffered = BytesIO()
                obs['screen'].save(buffered, format="PNG")
                screenshot_b64 = base64.b64encode(buffered.getvalue()).decode()
                
                # Update current screenshot
                self.current_screenshot = screenshot_b64
                
                # Save screenshot to file using existing naming pattern
                screenshot_filename = f"screenshot_{self.step_count}.png"
                screenshot_path = self.screenshot_dir / screenshot_filename
                obs['screen'].save(screenshot_path)
                
                # Log using existing pattern
                self.file_logger.info(f"Saved step {self.step_count} screenshot to {screenshot_path}")
                
                # Add to history with step number
                screenshot_entry = {
                    "step": self.step_count,
                    "screenshot": screenshot_b64,
                    "timestamp": time.time(),
                    "file_path": str(screenshot_path)
                }
                
                self.screenshot_history.append(screenshot_entry)
                
                # Keep only recent screenshots
                if len(self.screenshot_history) > self.max_screenshot_history:
                    self.screenshot_history = self.screenshot_history[-self.max_screenshot_history:]
    
    def _execute_actions(self, actions: list) -> Dict[str, Any]:
        """Execute multiple game actions and return results"""
        if not self.game_interface:
            return {"error": "Game not loaded"}
        
        self.file_logger.info("Received actions: %s", actions)
        
        results = []
        for i, action_str in enumerate(actions):
            try:
                # Convert action string to button dict
                action_dict = self._parse_action(action_str)
                
                # Execute action
                obs, _, _, _ = self.game_interface.step(action_dict, 100)  # 100 frames default
                
                # Update screenshot and state
                self._update_screenshot()
                self.step_count += 1
                self.game_state = "playing"
                
                results.append({
                    "success": True,
                    "action": action_str,
                    "step": self.step_count,
                    "action_index": i
                })
                
            except Exception as e:
                logger.error(f"Action execution failed at index {i}: {e}")
                results.append({
                    "success": False,
                    "action": action_str,
                    "error": str(e),
                    "action_index": i
                })
                # Continue with remaining actions even if one fails
        
        return {
            "success": True,
            "total_actions": len(actions),
            "results": results,
            "final_step": self.step_count
        }
    
    def _parse_action(self, action_str: str) -> Dict[str, bool]:
        """Parse action string to button dictionary"""
        # Handle multiple buttons: "A,B" or single button: "A"
        buttons = ['A', 'B', 'START', 'SELECT', 'UP', 'DOWN', 'LEFT', 'RIGHT']
        action_dict = {button: False for button in buttons}
        
        if action_str:
            pressed_buttons = [btn.strip().upper() for btn in action_str.split(',')]
            for button in pressed_buttons:
                if button in action_dict:
                    action_dict[button] = True
        
        return action_dict
    
    def _create_request_handler(self):
        """Create HTTP request handler"""
        server_instance = self
        
        class GBAGameHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith("/screenshots"):
                    self.send_screenshots()
                elif self.path == "/status":
                    self.send_status()
                elif self.path == "/health":
                    self.send_health()
                else:
                    self.send_error(404, "Not Found")
                    
            def do_POST(self):
                if self.path == "/actions":
                    self.execute_actions()
                elif self.path == "/reset":
                    self.reset_game()
                else:
                    self.send_error(404, "Not Found")
            
            def send_screenshots(self):
                """Return multiple recent screenshots"""
                # Parse query parameters for count
                from urllib.parse import urlparse, parse_qs
                parsed_url = urlparse(self.path)
                query_params = parse_qs(parsed_url.query)
                
                # Get count parameter (default to 1, max 20)
                count = 1
                if 'count' in query_params:
                    try:
                        count = int(query_params['count'][0])
                        count = max(1, min(count, 20))  # Limit between 1 and 20
                    except (ValueError, IndexError):
                        count = 1
                
                # Get recent screenshots
                recent_screenshots = server_instance.screenshot_history[-count:] if server_instance.screenshot_history else []
                
                response = {
                    "screenshots": recent_screenshots,
                    "count": len(recent_screenshots),
                    "current_step": server_instance.step_count,
                    "format": "base64_png"
                }
                
                self.send_json_response(response)
            
            def send_status(self):
                """Return game status"""
                response = {
                    "state": server_instance.game_state,
                    "step": server_instance.step_count,
                    "running": server_instance.is_running,
                    "screenshot_history_count": len(server_instance.screenshot_history)
                }
                self.send_json_response(response)
            
            def send_health(self):
                """Health check endpoint"""
                response = {"status": "healthy", "server": "gba_game_server"}
                self.send_json_response(response)
            
            def execute_actions(self):
                """Execute multiple game actions from POST data"""
                try:
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    data = json.loads(post_data.decode('utf-8'))
                    
                    # Expect actions array
                    actions = data.get('actions', [])
                    if not isinstance(actions, list):
                        raise ValueError("'actions' must be a list")
                    
                    if not actions:
                        result = {"error": "Empty actions list"}
                    else:
                        result = server_instance._execute_actions(actions)
                    
                    self.send_json_response(result)
                except Exception as e:
                    self.send_json_response({"error": str(e)})
            
            def reset_game(self):
                """Reset game state"""
                try:
                    if server_instance.game_interface:
                        server_instance.game_interface.reset()
                        server_instance._update_screenshot()
                        server_instance.step_count = 0
                        server_instance.game_state = "ready"
                    
                    response = {"success": True, "message": "Game reset"}
                    self.send_json_response(response)
                except Exception as e:
                    self.send_json_response({"error": str(e)})
            
            def send_json_response(self, data):
                """Send JSON response"""
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            
            def log_message(self, format, *args):
                # Suppress default HTTP logging
                pass
                
        return GBAGameHandler 