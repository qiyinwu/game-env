#!/usr/bin/env python3
"""
Unit tests for GBA Interface - Pure logic testing with minimal mocking

These tests focus on testing the GBAInterface logic without external dependencies.
Only mock PyBoy (external dependency), test all internal logic with real code.
"""

import pytest
import sys
import os
import tempfile
from unittest.mock import Mock, patch
from PIL import Image

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.emulators.gba.interface import GBAInterface


@pytest.mark.unit
class TestGBAInterfaceLogic:
    """Test GBA interface pure logic without external dependencies"""
    
    def test_button_mappings(self):
        """Test button mappings are correctly defined - no mock needed"""
        interface = GBAInterface()
        
        # Test all expected buttons exist
        expected_buttons = ['A', 'B', 'SELECT', 'START', 'RIGHT', 'LEFT', 'UP', 'DOWN']
        for button in expected_buttons:
            assert button in interface.BUTTON_MAP
            assert button in interface.RELEASE_MAP
        
        # Test mappings are different for press/release
        assert interface.BUTTON_MAP['A'] != interface.RELEASE_MAP['A']
        assert interface.BUTTON_MAP['B'] != interface.RELEASE_MAP['B']
    
    def test_get_available_buttons(self):
        """Test getting available buttons - no mock needed"""
        interface = GBAInterface()
        buttons = interface.get_available_buttons()
        
        assert isinstance(buttons, list)
        assert len(buttons) == 8
        assert 'A' in buttons
        assert 'B' in buttons
        assert 'START' in buttons
        assert 'SELECT' in buttons
        assert 'UP' in buttons
        assert 'DOWN' in buttons
        assert 'LEFT' in buttons
        assert 'RIGHT' in buttons
    
    def test_initialization(self):
        """Test interface initialization - no mock needed"""
        # Test with render=False
        interface = GBAInterface(render=False)
        assert interface.pyboy is None
        assert interface.render is False
        
        # Test with render=True
        interface = GBAInterface(render=True)
        assert interface.pyboy is None
        assert interface.render is True
    
    def test_load_game_file_not_found(self):
        """Test load_game with non-existent file - no mock needed"""
        interface = GBAInterface()
        result = interface.load_game("nonexistent_file.gba")
        assert result is False
    
    def test_operations_without_loaded_game(self):
        """Test operations fail gracefully without loaded game - no mock needed"""
        interface = GBAInterface()
        
        # These should raise RuntimeError
        with pytest.raises(RuntimeError, match="No ROM loaded"):
            interface.step({'A': True})
        
        with pytest.raises(RuntimeError, match="No ROM loaded"):
            interface.get_screen()
        
        with pytest.raises(RuntimeError, match="No ROM loaded"):
            interface.no_op()
        
        with pytest.raises(RuntimeError, match="Game not loaded"):
            interface.reset()


@pytest.mark.unit
class TestGBAInterfaceWithMockedPyBoy:
    """Test GBA interface with PyBoy mocked (only external dependency)"""
    
    @pytest.fixture
    def mock_pyboy(self):
        """Mock PyBoy - the only external dependency we need to mock"""
        with patch('src.emulators.gba.interface.PyBoy') as mock_pyboy_class:
            mock_pyboy_instance = Mock()
            mock_pyboy_instance.screen.image = Image.new('RGB', (160, 144), 'red')
            mock_pyboy_instance.tick = Mock()
            mock_pyboy_instance.send_input = Mock()
            mock_pyboy_instance.reset = Mock()
            mock_pyboy_instance.stop = Mock()
            mock_pyboy_instance.set_emulation_speed = Mock()
            
            mock_pyboy_class.return_value = mock_pyboy_instance
            yield mock_pyboy_instance
    
    def test_load_game_success(self, mock_pyboy):
        """Test successful game loading with mocked PyBoy"""
        interface = GBAInterface(render=False)
        
        # Create a temporary ROM file
        with tempfile.NamedTemporaryFile(suffix='.gba', delete=False) as temp_rom:
            temp_rom.write(b"fake rom data")
            temp_rom_path = temp_rom.name
        
        try:
            result = interface.load_game(temp_rom_path)
            assert result is True
            assert interface.pyboy is not None
            
            # Verify PyBoy was initialized correctly
            mock_pyboy.set_emulation_speed.assert_called_once_with(1)
            # Verify boot frames were run
            assert mock_pyboy.tick.call_count == 1200
            
        finally:
            os.unlink(temp_rom_path)
    
    def test_step_action_processing(self, mock_pyboy):
        """Test step action processing logic"""
        interface = GBAInterface(render=False)
        interface.pyboy = mock_pyboy  # Simulate loaded game
        
        # Test single button press
        action = {'A': True, 'B': False}
        obs, reward, done, info = interface.step(action, skip_frames=5)
        
        # Verify button press was sent
        mock_pyboy.send_input.assert_any_call(interface.BUTTON_MAP['A'])
        mock_pyboy.send_input.assert_any_call(interface.RELEASE_MAP['A'], delay=5)
        
        # Verify frames were advanced
        assert mock_pyboy.tick.call_count == 6  # skip_frames + 1
        
        # Verify observation structure
        assert 'screen' in obs
        assert 'buttons' in obs
        assert isinstance(obs['screen'], Image.Image)
        assert isinstance(obs['buttons'], list)
    
    def test_multiple_button_press(self, mock_pyboy):
        """Test multiple button press logic"""
        interface = GBAInterface(render=False)
        interface.pyboy = mock_pyboy
        
        # Test multiple buttons
        action = {'A': True, 'DOWN': True, 'B': False}
        interface.step(action, skip_frames=3)
        
        # Verify both buttons were pressed
        mock_pyboy.send_input.assert_any_call(interface.BUTTON_MAP['A'])
        mock_pyboy.send_input.assert_any_call(interface.RELEASE_MAP['A'], delay=3)
        mock_pyboy.send_input.assert_any_call(interface.BUTTON_MAP['DOWN'])
        mock_pyboy.send_input.assert_any_call(interface.RELEASE_MAP['DOWN'], delay=3)
        
        # Verify B button was not pressed (False)
        assert interface.BUTTON_MAP['B'] not in [call[0][0] for call in mock_pyboy.send_input.call_args_list]
    
    def test_no_op_functionality(self, mock_pyboy):
        """Test no-op functionality"""
        interface = GBAInterface(render=False)
        interface.pyboy = mock_pyboy
        
        obs, reward, done, info = interface.no_op(skip_frames=3)
        
        # Verify frames were advanced without input
        assert mock_pyboy.tick.call_count == 3
        # Verify no input was sent
        mock_pyboy.send_input.assert_not_called()
        
        # Verify observation structure
        assert 'screen' in obs
        assert 'buttons' in obs
    
    def test_get_screen(self, mock_pyboy):
        """Test screen capture"""
        interface = GBAInterface(render=False)
        interface.pyboy = mock_pyboy
        
        screen = interface.get_screen()
        
        assert isinstance(screen, Image.Image)
        assert screen.size == (160, 144)
    
    def test_reset_functionality(self, mock_pyboy):
        """Test game reset"""
        interface = GBAInterface(render=False)
        interface.pyboy = mock_pyboy
        # Set ROM path for reset functionality
        interface.current_rom_path = "test_rom.gba"
        
        # Mock the load_game method since reset calls it
        with patch.object(interface, 'load_game') as mock_load_game:
            mock_load_game.return_value = True
            obs = interface.reset()
            
            # Verify the game was stopped and reloaded
            mock_pyboy.stop.assert_called_once()
            mock_load_game.assert_called_once_with("test_rom.gba")
    
    def test_close_cleanup(self, mock_pyboy):
        """Test interface cleanup"""
        interface = GBAInterface(render=False)
        interface.pyboy = mock_pyboy
        
        interface.close()
        
        # Verify cleanup was called
        mock_pyboy.stop.assert_called_once()
        assert interface.pyboy is None
    
    def test_render_mode_initialization(self, mock_pyboy):
        """Test interface initialization with different render modes"""
        # Test with render=True
        interface_render = GBAInterface(render=True)
        temp_file = tempfile.NamedTemporaryFile(suffix='.gba', delete=False)
        temp_file.write(b"fake rom data")
        temp_file.close()
        
        try:
            interface_render.load_game(temp_file.name)
            # With render=True, PyBoy should be initialized
            assert interface_render.pyboy is not None
        finally:
            os.unlink(temp_file.name)
            
        # Test with render=False (default case)
        interface_no_render = GBAInterface(render=False)
        temp_file2 = tempfile.NamedTemporaryFile(suffix='.gba', delete=False)
        temp_file2.write(b"fake rom data")
        temp_file2.close()
        
        try:
            interface_no_render.load_game(temp_file2.name)
            # PyBoy should still be initialized even with render=False
            assert interface_no_render.pyboy is not None
        finally:
            os.unlink(temp_file2.name)


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 