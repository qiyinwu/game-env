from typing import Dict, Any, List, Tuple, Optional
from PIL import Image
import os
from pyboy import PyBoy
from pyboy.utils import WindowEvent
from src.emulators.interface_base import VideoGameBenchInterface

class GBAInterface(VideoGameBenchInterface):
    """Game Boy interface using PyBoy."""
    
    # Button mappings to PyBoy window events
    BUTTON_MAP = {
        'A': WindowEvent.PRESS_BUTTON_A,
        'B': WindowEvent.PRESS_BUTTON_B,
        'SELECT': WindowEvent.PRESS_BUTTON_SELECT,
        'START': WindowEvent.PRESS_BUTTON_START,
        'RIGHT': WindowEvent.PRESS_ARROW_RIGHT,
        'LEFT': WindowEvent.PRESS_ARROW_LEFT,
        'UP': WindowEvent.PRESS_ARROW_UP,
        'DOWN': WindowEvent.PRESS_ARROW_DOWN,
    }
    
    # Release button events
    RELEASE_MAP = {
        'A': WindowEvent.RELEASE_BUTTON_A,
        'B': WindowEvent.RELEASE_BUTTON_B,
        'SELECT': WindowEvent.RELEASE_BUTTON_SELECT,
        'START': WindowEvent.RELEASE_BUTTON_START,
        'RIGHT': WindowEvent.RELEASE_ARROW_RIGHT,
        'LEFT': WindowEvent.RELEASE_ARROW_LEFT,
        'UP': WindowEvent.RELEASE_ARROW_UP,
        'DOWN': WindowEvent.RELEASE_ARROW_DOWN,
    }
    
    def __init__(self, render: bool = False):
        super().__init__()
        self.pyboy = None
        self.render = render
        self.current_rom_path = None

    def load_game(self, rom_path: str, uncapped: bool = False) -> bool:
        """Load a Game Boy ROM."""
        try:
            if not os.path.exists(rom_path):
                print(f"ROM file not found: {rom_path}")
                return False
                
            # Initialize PyBoy with headless mode if not rendering
            self.pyboy = PyBoy(rom_path, window="SDL2" if self.render else "headless")
            self.pyboy.set_emulation_speed(1)
            
            # Save the ROM path for potential reset
            self.current_rom_path = rom_path
            
            # Run a few frames to get past the boot screen
            for _ in range(1200):
                self.pyboy.tick(15, render=self.render, sound=False)
            return True
            
        except Exception as e:
            print(f"Failed to load ROM: {e}")
            return False
    
    def no_op(self, skip_frames: int = 1):
        """
        Run the emulator for a specified number of frames without any input actions.
        This is useful for waiting or advancing the game state passively.

        Args:
            skip_frames: Number of frames to run with no input. Each frame advances
                        the game state by one tick. Default is 1 frame.
        """
        if not self.pyboy:
            raise RuntimeError("No ROM loaded")

        for _ in range(skip_frames):
            self.pyboy.tick(1, render=True)

        obs = self.get_observation()
        
        # For now, return dummy values for reward/done
        return obs, 0.0, False, {}
            
    def step(self, action: Dict[str, bool], skip_frames: int = 10) -> Tuple[Dict[str, Any], float, bool, Dict[str, Any]]:
        """
        Execute one frame with the given input action.
        
        Takes a dictionary mapping button names to boolean values indicating if they should be pressed,
        advances the emulator by the specified number of frames while applying those button presses,
        and returns the resulting game state.

        Args:
            action: Dictionary mapping button names (str) to pressed state (bool)
            skip_frames: Number of frames to advance after applying input. Default 10.
        """
        if not self.pyboy:
            raise RuntimeError("No ROM loaded")
            
        # Send the input actions
        for button, pressed in action.items():
            if pressed:
                self.pyboy.send_input(self.BUTTON_MAP[button])
                self.pyboy.send_input(self.RELEASE_MAP[button], delay=skip_frames)
            
        for _ in range(skip_frames+1):
            self.pyboy.tick(1, True)
        
        # Get new state
        obs = self.get_observation()
        
        # For now, return dummy values for reward/done
        return obs, 0.0, False, {}
        
    def get_screen(self) -> Image.Image:
        """Get the current screen as a PIL Image."""
        if not self.pyboy:
            raise RuntimeError("No ROM loaded")

        return self.pyboy.screen.image
        
    def get_available_buttons(self) -> List[str]:
        """Get list of available button inputs."""
        return list(self.BUTTON_MAP.keys())
        
    def close(self) -> None:
        """Clean up resources."""
        if self.pyboy:
            self.pyboy.stop()
            self.pyboy = None
            

    def reset(self):
        """Reset the game to initial state"""
        if not self.pyboy:
            raise RuntimeError("Game not loaded")
        
        # PyBoy doesn't have a direct reset method, so we reload the game
        current_rom_path = self.current_rom_path
        if current_rom_path:
            # Stop current game
            self.pyboy.stop()
            self.pyboy = None
            
            # Reload the game
            self.load_game(current_rom_path)
        else:
            raise RuntimeError("Cannot reset: no ROM path available")

    def get_observation(self) -> Optional[Dict[str, Any]]:
        """Get initial observation."""
        try:
            return {
                'screen': self.get_screen(),
                'buttons': self.get_available_buttons()
            }
        except:
            print("Failed to get initial observation")
            return None 