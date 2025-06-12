"""
Unit tests for Game State Persistence System
Tests for saving, loading, and managing game state checkpoints
"""

import pytest
import asyncio
import tempfile
import json
import pickle
import gzip
import time
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from PIL import Image
import io

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit

from src.persistence.game_state_persistence import (
    GameState, CheckpointInfo, GameStatePersistenceManager,
    GameBoyStateSaver, DOSStateSaver, PersistentGameEnvironment
)


@pytest.mark.unit
class TestGameState:
    """Test GameState data structure"""
    
    def test_game_state_creation(self):
        """Test creating a GameState object"""
        game_state = GameState(
            game_type="gameboy",
            game_name="pokemon_red",
            episode_id="test_episode",
            step_number=100,
            timestamp=time.time(),
            screen_data=b"screen_data",
            game_memory=b"memory_data",
            save_state=b"save_state",
            action_history=[{"A": True}],
            observation_history=[{"screen": "obs1"}],
            reward_history=[1.0],
            metadata={"level": 5}
        )
        
        assert game_state.game_type == "gameboy"
        assert game_state.game_name == "pokemon_red"
        assert game_state.episode_id == "test_episode"
        assert game_state.step_number == 100
        assert len(game_state.action_history) == 1
        assert len(game_state.observation_history) == 1
        assert len(game_state.reward_history) == 1
        assert game_state.metadata["level"] == 5


@pytest.mark.unit
class TestGameBoyStateSaver:
    """Test GameBoy state saving and loading"""
    
    @pytest.fixture
    def mock_gameboy_interface(self):
        """Create mock GameBoy interface"""
        interface = Mock()
        interface.pyboy = Mock()
        interface.pyboy.save_state = Mock(return_value=b"mock_save_state")
        interface.pyboy.load_state = Mock()
        interface.pyboy.memory = bytearray(b"mock_memory")
        return interface
    
    @pytest.mark.asyncio
    async def test_save_state_success(self, mock_gameboy_interface):
        """Test successful GameBoy state saving"""
        saver = GameBoyStateSaver()
        
        result = await saver.save_state(mock_gameboy_interface)
        
        assert result == b"mock_save_state"
        mock_gameboy_interface.pyboy.save_state.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_save_state_fallback_to_memory(self):
        """Test fallback to memory snapshot when save_state not available"""
        interface = Mock()
        interface.pyboy = Mock()
        interface.pyboy.save_state = Mock(side_effect=Exception("Save failed"))
        interface.pyboy.memory = bytearray(b"fallback_memory")
        
        saver = GameBoyStateSaver()
        result = await saver.save_state(interface)
        
        assert result == b"fallback_memory"
    
    @pytest.mark.asyncio
    async def test_load_state_success(self, mock_gameboy_interface):
        """Test successful GameBoy state loading"""
        saver = GameBoyStateSaver()
        
        result = await saver.load_state(mock_gameboy_interface, b"test_state")
        
        assert result is True
        mock_gameboy_interface.pyboy.load_state.assert_called_once_with(b"test_state")
    
    @pytest.mark.asyncio
    async def test_load_state_no_data(self, mock_gameboy_interface):
        """Test loading with no state data"""
        saver = GameBoyStateSaver()
        
        result = await saver.load_state(mock_gameboy_interface, None)
        
        assert result is False
    
    def test_get_memory_snapshot(self, mock_gameboy_interface):
        """Test getting memory snapshot"""
        saver = GameBoyStateSaver()
        
        result = saver.get_memory_snapshot(mock_gameboy_interface)
        
        assert result == b"mock_memory"


@pytest.mark.unit
class TestDOSStateSaver:
    """Test DOS state saving and loading"""
    
    @pytest.fixture
    def mock_dos_interface(self):
        """Create mock DOS interface"""
        interface = Mock()
        
        # Create a browser mock that specifically doesn't have 'page' attribute
        browser_mock = Mock(spec=['execute_script'])  # Only allow execute_script
        browser_mock.execute_script = Mock(return_value={
            "localStorage": "{}",
            "sessionStorage": "{}",
            "url": "http://example.com",
            "dosboxState": None
        })
        
        interface.browser = browser_mock
        
        return interface
    
    @pytest.mark.asyncio
    async def test_save_state_success(self, mock_dos_interface):
        """Test successful DOS state saving"""
        saver = DOSStateSaver()
        
        result = await saver.save_state(mock_dos_interface)
        
        assert result is not None
        assert isinstance(result, bytes)
        
        # Verify browser script was called
        mock_dos_interface.browser.execute_script.assert_called()
        
        # Verify the saved data can be parsed
        state_data = json.loads(result.decode('utf-8'))
        assert "localStorage" in state_data
        assert "sessionStorage" in state_data
    
    @pytest.mark.asyncio
    async def test_load_state_success(self, mock_dos_interface):
        """Test successful DOS state loading"""
        saver = DOSStateSaver()
        
        # Create test state data
        test_state = {
            "localStorage": '{"key1": "value1"}',
            "sessionStorage": '{"key2": "value2"}'
        }
        state_data = json.dumps(test_state).encode('utf-8')
        
        result = await saver.load_state(mock_dos_interface, state_data)
        
        assert result is True
        # Verify browser scripts were called to restore state
        assert mock_dos_interface.browser.execute_script.call_count >= 2
    
    def test_get_memory_snapshot(self, mock_dos_interface):
        """Test DOS memory snapshot (returns None as not supported)"""
        saver = DOSStateSaver()
        
        result = saver.get_memory_snapshot(mock_dos_interface)
        
        assert result is None


@pytest.mark.unit
class TestGameStatePersistenceManager:
    """Test the main persistence manager"""
    
    @pytest.fixture
    def temp_checkpoint_dir(self):
        """Create temporary checkpoint directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def persistence_manager(self, temp_checkpoint_dir):
        """Create persistence manager with temp directory"""
        return GameStatePersistenceManager(
            checkpoint_dir=temp_checkpoint_dir,
            auto_save_interval=10,
            max_checkpoints=3,
            compression=True
        )
    
    @pytest.fixture
    def mock_gameboy_interface(self):
        """Create mock GameBoy interface"""
        interface = Mock()
        interface.pyboy = Mock()
        interface.pyboy.save_state = Mock(return_value=b"mock_save_state")
        interface.pyboy.load_state = Mock()
        interface.pyboy.memory = bytearray(b"mock_memory")
        interface.game_name = "pokemon_red"
        interface.get_screen = Mock(return_value=self._create_test_image())
        return interface
    
    def _create_test_image(self):
        """Create a test PIL image"""
        img = Image.new('RGB', (160, 144), color='red')
        return img
    
    @pytest.mark.asyncio
    async def test_save_checkpoint_success(self, persistence_manager, mock_gameboy_interface):
        """Test successful checkpoint saving"""
        action_history = [{"A": True}, {"B": True}]
        observation_history = [{"screen": "obs1"}, {"screen": "obs2"}]
        reward_history = [1.0, 2.0]
        
        checkpoint_id = await persistence_manager.save_checkpoint(
            game_interface=mock_gameboy_interface,
            episode_id="test_episode",
            step_number=50,
            action_history=action_history,
            observation_history=observation_history,
            reward_history=reward_history,
            metadata={"test": "data"}
        )
        
        assert checkpoint_id is not None
        assert "test_episode_step_50" in checkpoint_id
        
        # Verify checkpoint file exists
        checkpoint_files = list(persistence_manager.checkpoint_dir.glob("*.pkl.gz"))
        assert len(checkpoint_files) == 1
        
        # Verify index was updated
        assert len(persistence_manager.checkpoints) == 1
        assert persistence_manager.checkpoints[0].checkpoint_id == checkpoint_id
    
    @pytest.mark.asyncio
    async def test_load_checkpoint_success(self, persistence_manager, mock_gameboy_interface):
        """Test successful checkpoint loading"""
        # First save a checkpoint
        action_history = [{"A": True}]
        observation_history = [{"screen": "obs1"}]
        reward_history = [1.0]
        
        checkpoint_id = await persistence_manager.save_checkpoint(
            game_interface=mock_gameboy_interface,
            episode_id="test_episode",
            step_number=25,
            action_history=action_history,
            observation_history=observation_history,
            reward_history=reward_history
        )
        
        # Now load it
        result = await persistence_manager.load_checkpoint(checkpoint_id, mock_gameboy_interface)
        
        assert result is not None
        game_state, success = result
        assert success is True
        assert game_state.episode_id == "test_episode"
        assert game_state.step_number == 25
        assert len(game_state.action_history) == 1
        assert game_state.action_history[0] == {"A": True}
    
    @pytest.mark.asyncio
    async def test_load_nonexistent_checkpoint(self, persistence_manager, mock_gameboy_interface):
        """Test loading a checkpoint that doesn't exist"""
        result = await persistence_manager.load_checkpoint("nonexistent_id", mock_gameboy_interface)
        
        assert result is None
    
    def test_list_checkpoints(self, persistence_manager):
        """Test listing checkpoints"""
        # Initially empty
        checkpoints = persistence_manager.list_checkpoints()
        assert len(checkpoints) == 0
        
        # Add some mock checkpoints
        mock_checkpoint = CheckpointInfo(
            checkpoint_id="test_id",
            game_state=GameState(
                game_type="gameboy",
                game_name="test",
                episode_id="episode1",
                step_number=10,
                timestamp=1234567890.0,
                screen_data=b"",
                game_memory=None,
                save_state=None,
                action_history=[],
                observation_history=[],
                reward_history=[],
                metadata={}
            ),
            file_path=Path("test.pkl"),
            created_at=1234567890.0,
            file_size=100,
            checksum="abc123"
        )
        persistence_manager.checkpoints.append(mock_checkpoint)
        
        checkpoints = persistence_manager.list_checkpoints()
        assert len(checkpoints) == 1
        assert checkpoints[0].checkpoint_id == "test_id"
        
        # Test filtering by episode_id
        checkpoints = persistence_manager.list_checkpoints("episode1")
        assert len(checkpoints) == 1
        
        checkpoints = persistence_manager.list_checkpoints("nonexistent")
        assert len(checkpoints) == 0
    
    def test_get_latest_checkpoint(self, persistence_manager):
        """Test getting the latest checkpoint for an episode"""
        # Add mock checkpoints with different step numbers
        for step in [10, 30, 20]:
            mock_checkpoint = CheckpointInfo(
                checkpoint_id=f"test_id_{step}",
                game_state=GameState(
                    game_type="gameboy",
                    game_name="test",
                    episode_id="episode1",
                    step_number=step,
                    timestamp=1234567890.0,
                    screen_data=b"",
                    game_memory=None,
                    save_state=None,
                    action_history=[],
                    observation_history=[],
                    reward_history=[],
                    metadata={}
                ),
                file_path=Path(f"test_{step}.pkl"),
                created_at=1234567890.0,
                file_size=100,
                checksum="abc123"
            )
            persistence_manager.checkpoints.append(mock_checkpoint)
        
        latest = persistence_manager.get_latest_checkpoint("episode1")
        assert latest is not None
        assert latest.game_state.step_number == 30  # Highest step number
        
        # Test with nonexistent episode
        latest = persistence_manager.get_latest_checkpoint("nonexistent")
        assert latest is None
    
    def test_cleanup_old_checkpoints(self, persistence_manager):
        """Test cleanup of old checkpoints"""
        # Add more checkpoints than max_checkpoints (3)
        for i in range(5):
            mock_checkpoint = CheckpointInfo(
                checkpoint_id=f"test_id_{i}",
                game_state=GameState(
                    game_type="gameboy",
                    game_name="test",
                    episode_id="episode1",
                    step_number=i,
                    timestamp=1234567890.0 + i,
                    screen_data=b"",
                    game_memory=None,
                    save_state=None,
                    action_history=[],
                    observation_history=[],
                    reward_history=[],
                    metadata={}
                ),
                file_path=Path(f"test_{i}.pkl"),
                created_at=1234567890.0 + i,
                file_size=100,
                checksum="abc123"
            )
            persistence_manager.checkpoints.append(mock_checkpoint)
        
        # Trigger cleanup
        persistence_manager._cleanup_old_checkpoints()
        
        # Should only keep max_checkpoints (3)
        assert len(persistence_manager.checkpoints) == 3
        
        # Should keep the most recent ones
        remaining_ids = [cp.checkpoint_id for cp in persistence_manager.checkpoints]
        assert "test_id_2" in remaining_ids
        assert "test_id_3" in remaining_ids
        assert "test_id_4" in remaining_ids
    
    def test_detect_game_type(self, persistence_manager):
        """Test game type detection"""
        # GameBoy interface - has pyboy attribute only
        class GameBoyInterface:
            def __init__(self):
                self.pyboy = Mock()
        
        gb_interface = GameBoyInterface()
        assert persistence_manager._detect_game_type(gb_interface) == "gameboy"
        
        # DOS interface - has browser attribute only
        class DOSInterface:
            def __init__(self):
                self.browser = Mock()
        
        dos_interface = DOSInterface()
        assert persistence_manager._detect_game_type(dos_interface) == "dos"
        
        # Unknown interface - has neither pyboy nor browser
        class UnknownInterface:
            def __init__(self):
                self.some_other_attr = Mock()
        
        unknown_interface = UnknownInterface()
        assert persistence_manager._detect_game_type(unknown_interface) == "unknown"


@pytest.mark.unit
class TestPersistentGameEnvironment:
    """Test the persistent game environment wrapper"""
    
    @pytest.fixture
    def temp_checkpoint_dir(self):
        """Create temporary checkpoint directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def persistence_manager(self, temp_checkpoint_dir):
        """Create persistence manager"""
        return GameStatePersistenceManager(
            checkpoint_dir=temp_checkpoint_dir,
            auto_save_interval=2,  # Save every 2 steps for testing
            max_checkpoints=3
        )
    
    @pytest.fixture
    def mock_base_env(self):
        """Create mock base environment"""
        env = Mock()
        env.game_interface = Mock()
        env.game_interface.pyboy = Mock()
        env.game_interface.pyboy.save_state = Mock(return_value=b"mock_save")
        env.game_interface.pyboy.load_state = Mock()
        env.game_interface.game_name = "test_game"
        env.reset = AsyncMock(return_value={"screen": "initial_obs"})
        env.step = AsyncMock(return_value=({"screen": "obs"}, 1.0, False, {}))
        env.get_observation = AsyncMock(return_value={"screen": "current_obs"})
        env._format_observation = Mock(side_effect=lambda x: x)
        return env
    
    @pytest.fixture
    def persistent_env(self, mock_base_env, persistence_manager):
        """Create persistent game environment"""
        return PersistentGameEnvironment(
            base_env=mock_base_env,
            persistence_manager=persistence_manager,
            episode_id="test_episode"
        )
    
    @pytest.mark.asyncio
    async def test_reset_normal(self, persistent_env):
        """Test normal environment reset"""
        obs = await persistent_env.reset()
        
        assert obs == {"screen": "initial_obs"}
        assert persistent_env.step_count == 0
        assert len(persistent_env.action_history) == 0
        assert len(persistent_env.observation_history) == 1
        assert len(persistent_env.reward_history) == 0
    
    @pytest.mark.asyncio
    async def test_step_with_auto_checkpoint(self, persistent_env):
        """Test stepping with automatic checkpoint saving"""
        await persistent_env.reset()
        
        # Step 1 - no checkpoint yet
        obs, reward, done, info = await persistent_env.step({"A": True})
        assert "checkpoint_saved" not in info
        assert persistent_env.step_count == 1
        
        # Step 2 - should trigger checkpoint (auto_save_interval=2)
        obs, reward, done, info = await persistent_env.step({"B": True})
        assert "checkpoint_saved" in info
        assert persistent_env.step_count == 2
        
        # Verify history
        assert len(persistent_env.action_history) == 2
        assert persistent_env.action_history[0] == {"A": True}
        assert persistent_env.action_history[1] == {"B": True}
    
    @pytest.mark.asyncio
    async def test_save_checkpoint_now(self, persistent_env):
        """Test manual checkpoint saving"""
        await persistent_env.reset()
        await persistent_env.step({"A": True})
        
        checkpoint_id = await persistent_env.save_checkpoint_now()
        
        assert checkpoint_id is not None
        assert "test_episode" in checkpoint_id


@pytest.mark.unit
class TestIntegration:
    """Integration tests for the complete persistence system"""
    
    @pytest.fixture
    def temp_checkpoint_dir(self):
        """Create temporary checkpoint directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.mark.asyncio
    async def test_full_save_load_cycle(self, temp_checkpoint_dir):
        """Test complete save and load cycle"""
        # Create persistence manager
        manager = GameStatePersistenceManager(
            checkpoint_dir=temp_checkpoint_dir,
            auto_save_interval=10,
            max_checkpoints=5
        )
        
        # Create mock game interface
        interface = Mock()
        interface.pyboy = Mock()
        interface.pyboy.save_state = Mock(return_value=b"test_save_state")
        interface.pyboy.load_state = Mock()
        interface.pyboy.memory = bytearray(b"test_memory")
        interface.game_name = "test_game"
        interface.get_screen = Mock(return_value=Image.new('RGB', (160, 144), 'blue'))
        
        # Save checkpoint
        action_history = [{"A": True}, {"B": True}, {"START": True}]
        observation_history = [{"screen": f"obs_{i}"} for i in range(3)]
        reward_history = [1.0, 2.0, 3.0]
        
        checkpoint_id = await manager.save_checkpoint(
            game_interface=interface,
            episode_id="integration_test",
            step_number=100,
            action_history=action_history,
            observation_history=observation_history,
            reward_history=reward_history,
            metadata={"level": 5, "score": 1000}
        )
        
        assert checkpoint_id is not None
        
        # Verify checkpoint file exists and has correct structure
        checkpoint_files = list(temp_checkpoint_dir.glob("*.pkl.gz"))
        assert len(checkpoint_files) == 1
        
        # Load checkpoint
        result = await manager.load_checkpoint(checkpoint_id, interface)
        assert result is not None
        
        game_state, success = result
        assert success is True
        
        # Verify loaded data matches saved data
        assert game_state.episode_id == "integration_test"
        assert game_state.step_number == 100
        assert game_state.game_name == "test_game"
        assert game_state.game_type == "gameboy"
        assert game_state.action_history == action_history
        assert game_state.observation_history == observation_history
        assert game_state.reward_history == reward_history
        assert game_state.metadata["level"] == 5
        assert game_state.metadata["score"] == 1000
        
        # Verify game state was restored
        interface.pyboy.load_state.assert_called_once_with(b"test_save_state")
    
    @pytest.mark.asyncio
    async def test_checkpoint_index_persistence(self, temp_checkpoint_dir):
        """Test that checkpoint index persists across manager instances"""
        # Create first manager and save checkpoint
        manager1 = GameStatePersistenceManager(checkpoint_dir=temp_checkpoint_dir)
        
        interface = Mock()
        interface.pyboy = Mock()
        interface.pyboy.save_state = Mock(return_value=b"state1")
        interface.game_name = "test"
        
        checkpoint_id = await manager1.save_checkpoint(
            game_interface=interface,
            episode_id="persistence_test",
            step_number=50,
            action_history=[],
            observation_history=[],
            reward_history=[]
        )
        
        # Create second manager (simulating restart)
        manager2 = GameStatePersistenceManager(checkpoint_dir=temp_checkpoint_dir)
        
        # Should load existing checkpoints
        checkpoints = manager2.list_checkpoints()
        assert len(checkpoints) == 1
        assert checkpoints[0].checkpoint_id == checkpoint_id
        
        # Should be able to load the checkpoint
        result = await manager2.load_checkpoint(checkpoint_id, interface)
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 