#!/usr/bin/env python3
import argparse
import yaml
import asyncio
import os
import sys
import webbrowser
import signal
import time
import socket
from typing import Optional, Dict, Any
from PIL import Image
from pathlib import Path
from src.llm.prompts import DOS_PROMPT
from src.utils import hash_image

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv not installed. Environment variables must be set manually.")

# Global variables for clean shutdown
game_instance = None

def find_free_port(start_port=None):
    """Find a free port on localhost, starting from start_port if specified"""
    if start_port:
        # First try the requested port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('', start_port))
                s.listen(1)
                return start_port
            except OSError:
                # Port is in use, find a free one
                print(f"Port {start_port} is already in use, finding a free port...")
    
    # Find any free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def parse_args():
    parser = argparse.ArgumentParser(description="Game Emulation and Evaluation with LLMs")
    
    # VideoGameBench emulator attributes
    parser.add_argument("--emulator", choices=["dos", "gba"],
                       help="Which emulator to use ('dos' or 'gba'). Overwritten if config is specified.")
    parser.add_argument("--game", type=str, 
                       help="Name or URL of a js-dos game bundle to run or GBA game to load")
    parser.add_argument("--lite", action="store_true", 
                       help="Lite-mode, so not real time. Game pauses between actions.")
    parser.add_argument("--max-steps", type=int, default=15000, 
                       help="Maximum number of steps to run")

    # Common arguments
    parser.add_argument("--enable-ui", action="store_true", 
                       help="Enable the UI for the agent")
    parser.add_argument("--threshold", type=float,  
                       help="Threshold for checkpoint progress")
    parser.add_argument("--model", type=str, default="gpt-4o",
                       help="The LLM model to use (for LiteLLM names). Default is gpt-4o")
    parser.add_argument("--headless", action="store_true", 
                       help="Run the emulator without visual display")
    parser.add_argument("--config-folder", type=str, default="configs/",
                       help="Path to the config folder")
    parser.add_argument("--max-tokens", type=int, default=1024, 
                       help="The maximum number of tokens to generate")
    parser.add_argument("--temperature", type=float, default=0.7, 
                       help="The temperature for LLM generation")
    parser.add_argument("--num-screenshots-per-action", type=int, default=0, 
                       help="Number of screenshots to take per action to add in context. 0 has default behavior described in the paper.")
    parser.add_argument("--max-context-size", type=int, default=20, 
                       help="Maximum number of messages in the context window. Default is 20.")

    # LiteLLM + Ollama args
    parser.add_argument("--api-key", type=str, 
                       help="API key for the chosen LLM provider")
    parser.add_argument("--api-base", type=str, default=None,
                       help="API base URL for Ollama or other providers")

    # DOS-specific arguments
    parser.add_argument("--port", type=int, default=8000, 
                       help="Port to run the server on (DOS only)")
    parser.add_argument("--task", type=str, default="",
                       help="The task for the agent to execute (DOS only)")
    parser.add_argument("--url", type=str, default="", 
                       help="The URL to start from (DOS only)")
    parser.add_argument("--website-only", action="store_true", 
                       help="Just open the website without agent interaction (DOS only)")
    
    # GBA-specific arguments
    parser.add_argument("--step-delay", type=float, default=0.0, 
                       help="Delay between steps in seconds (GBA only)")
    parser.add_argument("--skip-frames", type=int, default=1, 
                       help="Number of frames to skip per step (GBA only)")
    parser.add_argument("--fake-actions", action="store_true", 
                       help="Use random actions instead of calling the LLM (GBA only)")
    parser.add_argument("--history-tokens", type=int, default=4000, 
                       help="Maximum tokens in conversation history (GBA only)")
    parser.add_argument("--action-frames", type=int, default=15,
                       help="Number of frames to run each action for (GBA only)")
    parser.add_argument("--server-mode", action="store_true",
                       help="Run GBA game as HTTP server for external control (GBA only)")
    parser.add_argument("--server-port", type=int, default=8080,
                       help="Port for server mode (default: 8080)")
    parser.add_argument("--log-dir", type=str, 
                       help="Directory to store logs and screenshots (GBA only)")

    # Parse arguments
    args = parser.parse_args()

    return args

def load_game_config(args):
    """Load game configuration and prompt from the appropriate config folder."""
    # DOS-specific game defaults
    args.press_key_delay = 100

    if not args.game or not args.config_folder:
        print(f"No game or config folder specified. Exiting.")
        return args

    # Determine config path based on emulator type
    config_base = Path(args.config_folder)
    config_dir = config_base / args.game
    config_file = config_dir / "config.yaml"
    prompt_file = config_dir / "prompt.txt"
    # Try loading checkpoints if they exist
    checkpoint_dir = config_dir / "checkpoints"
    if os.path.exists(checkpoint_dir):
        try:
            # Get all image files and sort numerically
            checkpoint_files = sorted(
                [f for f in checkpoint_dir.glob("*.png")],
                key=lambda x: int(x.stem)  # Use stem to get filename without extension
            )
            print("Checkpoint files:", checkpoint_files)
            if checkpoint_files:
                checkpoint_hashes = []
                for checkpoint in checkpoint_files:
                    img = Image.open(checkpoint)
                    hash_str = hash_image(img)
                    checkpoint_hashes.append(hash_str)
                args.checkpoints = checkpoint_hashes
            else:
                args.checkpoints = None
        except:
            args.checkpoints = None
    else:
        args.checkpoints = None
    
    print(f"Loading config from {config_file}")
    try:
        # Load YAML config
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
            
        # Load prompt if it exists
        if prompt_file.exists():
            with open(prompt_file, 'r', encoding='utf-8') as f:
                config['task_prompt'] = f.read().strip()
        else:
            print(f"Warning: No prompt file found at {prompt_file}")
            config['task_prompt'] = ""
            
        # Update args with config values, preserving command-line overrides
        for key, value in config.items():
            # Only update if not explicitly set in command line
            if not getattr(args, key, None):
                setattr(args, key, value)
                
        # Special handling for DOS games
        if args.emulator == "dos":
            html_file = config_dir / "game.html"
            if html_file.exists():
                with open(html_file, 'r') as f:
                    args.custom_html = f.read()
            else:
                args.custom_html = None
                
    except FileNotFoundError:
        print(f"No config file found at {config_file}")
        print(f"Using default configuration for {args.game}")
    except Exception as e:
        print(f"Error loading config: {e}")
        
    return args

def handle_shutdown_signal(sig, frame):
    """Handle shutdown signals for clean exit."""
    print("\nShutdown signal received. Cleaning up...")
        
    # Close any active screen recorder
    if hasattr(game_instance, 'monitor') and game_instance.monitor:
        if game_instance.monitor.screen_recorder:
            game_instance.monitor.screen_recorder.close()
    
    sys.exit(0)

async def videogamebench_start():
    """Main async entry point."""
    args = parse_args()
    args = load_game_config(args)

    if args.model == "gpt-4o":
        args.model = "gpt-4o"
    elif args.model == "claude-3.7":
        args.model = "claude-3-7-sonnet-20250219"
    elif args.model == "gemini-2.0-flash":
        args.model = "gemini/gemini-2.0-flash"
    elif args.model == "llama4":
        args.model = "together_ai/meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"

    if args.emulator == "dos":
        from src.run_vgbench_dos import run_dos_emulator
        await run_dos_emulator(args)
    elif args.emulator == "gba":
        if args.server_mode:
            await run_gba_server(args)
        else:
            from src.run_vgbench_gb import run_gba_emulator
            await run_gba_emulator(args)
    else:
        print("No emulator specified. Exiting.")
        sys.exit(1)

def run_gba_server(args, test_log_dir=None):
    """Run GBA game server"""
    from src.emulators.gba.game_server import GBAGameServer
    
    # Try multiple ROM file extensions
    rom_extensions = ['.gba', '.gb', '.gbc']
    rom_path = None
    attempted_paths = []
    
    for ext in rom_extensions:
        potential_path = f"roms/{args.game}{ext}"
        attempted_paths.append(potential_path)
        if os.path.exists(potential_path):
            rom_path = potential_path
            break
    
    if not rom_path:
        print(f"ROM file not found. Tried: {', '.join(attempted_paths)}")
        sys.exit(1)
    
    # Find a free port, starting with the requested port
    free_port = find_free_port(args.server_port)
    if free_port != args.server_port:
        print(f"Port {args.server_port} was in use, using port {free_port} instead")
    
    print(f"Starting GBA server on port {free_port}")
    print(f"Using ROM: {rom_path}")
    
    # Create server with custom log directory for tests or default for production
    if test_log_dir:
        server = GBAGameServer(
            port=free_port,
            log_dir=test_log_dir,
            game_name=args.game
        )
    elif hasattr(args, 'log_dir') and args.log_dir:
        # Use custom log directory from command line
        server = GBAGameServer(
            port=free_port,
            log_dir=args.log_dir,
            game_name=args.game
        )
    else:
        # Production mode - use existing log structure
        server = GBAGameServer(
            port=free_port,
            game_name=args.game
        )
    
    try:
        result = server.start(rom_path)
        print(result)
        
        # Keep server running
        while server.is_running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.stop()
        print("Server stopped")

if __name__ == "__main__":
    # Register signal handlers for clean shutdown
    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)
    
    # Run the main function
    try:
        asyncio.run(videogamebench_start())
    except KeyboardInterrupt:
        print("\nProgram interrupted. Cleaning up...")
