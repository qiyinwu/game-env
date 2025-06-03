"""
Integration tests for the persistence system

These tests verify that all components work together correctly
in realistic scenarios.
"""

import pytest
import tempfile
import asyncio
import time
from pathlib import Path

from src.persistence import (
    PathBasedStorage,
    EnhancedPersistenceManager,
    GameState
)


class RealGameBoyInterface:
    """Real GameBoy interface for integration testing"""
    
    def __init__(self, game_name="pokemon_red"):
        self.game_name = game_name
        self.pyboy = RealPyBoyEmulator()
    
    def get_screen(self):
        return b"real_gameboy_screen_data"


class RealPyBoyEmulator:
    """Real PyBoy emulator for integration testing"""
    
    def __init__(self):
        self.memory = bytearray(b"real_gameboy_memory" * 100)
        self.state_data = b"real_gameboy_save_state"
    
    def save_state(self):
        return self.state_data
    
    def load_state(self, state_data):
        return state_data == self.state_data


class RealDOSInterface:
    """Real DOS interface for integration testing"""
    
    def __init__(self, game_name="doom"):
        self.game_name = game_name
        self.browser = RealBrowserInterface()
    
    def get_screen(self):
        return b"real_dos_screen_data"


class RealBrowserInterface:
    """Real browser interface for integration testing"""
    
    def __init__(self):
        self.page = None  # Use execute_script path
        self.game_state = {
            "level": "E1M1",
            "score": 1500,
            "inventory": ["shotgun", "keycard"]
        }
    
    def execute_script(self, script):
        return self.game_state


def create_real_gameboy_interface():
    """Create a real GameBoy interface for integration testing"""
    return RealGameBoyInterface("pokemon_red")


def create_real_dos_interface():
    """Create a real DOS interface for integration testing"""
    return RealDOSInterface("doom")


class TestBasicPersistenceIntegration:
    """Integration tests for basic persistence functionality"""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.mark.asyncio
    async def test_complete_gameboy_session_integration(self, temp_storage_dir):
        """Test complete GameBoy gaming session with persistence"""
        # Create persistence manager
        manager = EnhancedPersistenceManager(
            storage_path=temp_storage_dir,
            auto_save_interval=50,
            max_checkpoints=5
        )
        
        # Create mock game interface
        mock_interface = create_real_gameboy_interface()
        
        # Save a checkpoint
        checkpoint_id = await manager.save_checkpoint(
            game_interface=mock_interface,
            episode_id="integration_test_episode",
            step_number=100,
            action_history=[{"A": True}, {"B": False}],
            observation_history=[{"screen": "frame1"}, {"screen": "frame2"}],
            reward_history=[1.0, 2.0],
            metadata={"level": 1, "score": 500}
        )
        
        # Verify checkpoint was created
        assert checkpoint_id is not None
        assert "integration_test_episode_step_100" in checkpoint_id
        
        # Load the checkpoint
        result = await manager.load_checkpoint(checkpoint_id, mock_interface)
        assert result is not None
        
        game_state, success = result
        assert success is True
        assert game_state.episode_id == "integration_test_episode"
        assert game_state.step_number == 100
        assert game_state.game_name == "pokemon_red"
        
        # List checkpoints
        checkpoints = await manager.list_checkpoints()
        assert len(checkpoints) == 1
        assert checkpoints[0]["checkpoint_id"] == checkpoint_id
    
    @pytest.mark.asyncio
    async def test_dos_session_integration(self, temp_storage_dir):
        """Test DOS game session integration"""
        manager = EnhancedPersistenceManager(
            storage_path=temp_storage_dir,
            auto_save_interval=25,
            max_checkpoints=3
        )
        
        mock_interface = create_real_dos_interface()
        
        # Save multiple checkpoints
        checkpoint_ids = []
        for i in range(3):
            checkpoint_id = await manager.save_checkpoint(
                game_interface=mock_interface,
                episode_id="dos_integration_test",
                step_number=i * 10,
                action_history=[{"step": i}],
                observation_history=[{"frame": i}],
                reward_history=[float(i)],
                metadata={"iteration": i}
            )
            assert checkpoint_id is not None
            checkpoint_ids.append(checkpoint_id)
        
        # Verify all checkpoints exist
        checkpoints = await manager.list_checkpoints("dos_integration_test")
        assert len(checkpoints) == 3
        
        # Test loading each checkpoint
        for i, checkpoint_id in enumerate(checkpoint_ids):
            result = await manager.load_checkpoint(checkpoint_id, mock_interface)
            assert result is not None
            game_state, success = result
            assert success is True
            assert game_state.step_number == i * 10


class TestPathBasedStorageIntegration:
    """Integration tests for path-based storage"""
    
    @pytest.mark.asyncio
    async def test_local_storage_full_cycle(self):
        """Test complete local storage cycle"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = PathBasedStorage(temp_dir)
            
            # Test data
            test_data = b"integration_test_checkpoint_data"
            test_metadata = {
                "episode_id": "integration_test",
                "step_number": 42,
                "game_type": "gameboy"
            }
            
            # Upload checkpoint
            success = await storage.upload_checkpoint("integration_cp_001", test_data, test_metadata)
            assert success is True
            
            # Verify file exists
            checkpoint_file = storage.checkpoints_dir / "integration_cp_001.pkl.gz"
            assert checkpoint_file.exists()
            
            # Download checkpoint
            downloaded = await storage.download_checkpoint("integration_cp_001")
            assert downloaded == test_data
            
            # List checkpoints
            checkpoints = await storage.list_checkpoints()
            assert len(checkpoints) == 1
            assert checkpoints[0]["checkpoint_id"] == "integration_cp_001"
            assert checkpoints[0]["metadata"] == test_metadata
            
            # Delete checkpoint
            deleted = await storage.delete_checkpoint("integration_cp_001")
            assert deleted is True
            assert not checkpoint_file.exists()
            
            # Verify empty after deletion
            checkpoints = await storage.list_checkpoints()
            assert len(checkpoints) == 0
    
    @pytest.mark.asyncio
    async def test_cns_storage_fallback_integration(self):
        """Test CNS storage fallback integration"""
        storage = PathBasedStorage("cns://integration/test/path")
        
        # Should fall back to local storage
        assert storage.scheme == "file"
        assert "cns_fallback" in str(storage.local_path)
        
        # Test basic operations work with fallback
        test_data = b"cns_fallback_test_data"
        test_metadata = {"test": "cns_fallback"}
        
        success = await storage.upload_checkpoint("cns_test", test_data, test_metadata)
        assert success is True
        
        downloaded = await storage.download_checkpoint("cns_test")
        assert downloaded == test_data


class TestEnhancedManagerIntegration:
    """Integration tests for enhanced persistence manager"""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.mark.asyncio
    async def test_auto_cleanup_integration(self, temp_storage_dir):
        """Test automatic cleanup functionality integration"""
        manager = EnhancedPersistenceManager(
            storage_path=temp_storage_dir,
            auto_save_interval=10,
            max_checkpoints=3  # Small limit to test cleanup
        )
        
        mock_interface = create_real_gameboy_interface()
        
        # Save more checkpoints than max_checkpoints
        checkpoint_ids = []
        for i in range(5):  # More than max of 3
            checkpoint_id = await manager.save_checkpoint(
                game_interface=mock_interface,
                episode_id="cleanup_integration_test",
                step_number=i * 10,
                action_history=[{"step": i}],
                observation_history=[{"frame": i}],
                reward_history=[float(i)],
                metadata={"iteration": i}
            )
            checkpoint_ids.append(checkpoint_id)
            # Small delay to ensure different timestamps
            await asyncio.sleep(0.01)
        
        # Verify cleanup occurred
        remaining_checkpoints = await manager.list_checkpoints("cleanup_integration_test")
        assert len(remaining_checkpoints) <= manager.max_checkpoints
        
        # Verify the remaining checkpoints are the most recent ones
        remaining_steps = [cp["metadata"]["step_number"] for cp in remaining_checkpoints]
        assert max(remaining_steps) == 40  # Latest step should be preserved
    
    @pytest.mark.asyncio
    async def test_multiple_episodes_integration(self, temp_storage_dir):
        """Test handling multiple episodes integration"""
        manager = EnhancedPersistenceManager(
            storage_path=temp_storage_dir,
            auto_save_interval=10,
            max_checkpoints=5
        )
        
        mock_interface = create_real_gameboy_interface()
        
        # Create checkpoints for multiple episodes
        episodes = ["episode_1", "episode_2", "episode_3"]
        all_checkpoint_ids = {}
        
        for episode in episodes:
            episode_checkpoints = []
            for step in range(3):
                checkpoint_id = await manager.save_checkpoint(
                    game_interface=mock_interface,
                    episode_id=episode,
                    step_number=step * 10,
                    action_history=[{"episode": episode, "step": step}],
                    observation_history=[{"episode_frame": f"{episode}_{step}"}],
                    reward_history=[float(step)],
                    metadata={"episode": episode, "step": step}
                )
                episode_checkpoints.append(checkpoint_id)
            all_checkpoint_ids[episode] = episode_checkpoints
        
        # Verify each episode has its checkpoints
        for episode in episodes:
            checkpoints = await manager.list_checkpoints(episode)
            assert len(checkpoints) == 3
            
            # Verify episode isolation
            for cp in checkpoints:
                assert cp["metadata"]["episode_id"] == episode
        
        # Verify total checkpoints
        all_checkpoints = await manager.list_checkpoints()
        assert len(all_checkpoints) == 9  # 3 episodes × 3 checkpoints each
    
    @pytest.mark.asyncio
    async def test_error_recovery_integration(self, temp_storage_dir):
        """Test error recovery integration"""
        manager = EnhancedPersistenceManager(
            storage_path=temp_storage_dir,
            auto_save_interval=10,
            max_checkpoints=5
        )
        
        # Test with broken interface
        broken_interface = RealGameBoyInterface()
        broken_interface.pyboy = None  # This will cause issues
        broken_interface.game_name = "broken_game"
        
        def broken_get_screen():
            return b"broken_screen"
        broken_interface.get_screen = broken_get_screen
        
        # Should handle gracefully
        checkpoint_id = await manager.save_checkpoint(
            game_interface=broken_interface,
            episode_id="error_recovery_test",
            step_number=1,
            action_history=[],
            observation_history=[],
            reward_history=[]
        )
        
        # Should still create checkpoint despite errors
        assert checkpoint_id is not None
        
        # Verify checkpoint exists but with limited data
        checkpoints = await manager.list_checkpoints("error_recovery_test")
        assert len(checkpoints) == 1


class TestStorageConfigurationIntegration:
    """Integration tests for different storage configurations"""
    
    def test_local_path_configuration(self):
        """Test local path configuration integration"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = PathBasedStorage(temp_dir)
            assert storage.scheme == "file"
            assert storage.local_path == Path(temp_dir).resolve()
            assert storage.checkpoints_dir.exists()
            assert storage.metadata_dir.exists()
            assert storage.index_file.exists()
    
    def test_file_url_configuration(self):
        """Test file URL configuration integration"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_url = f"file://{temp_dir}"
            storage = PathBasedStorage(file_url)
            assert storage.scheme == "file"
            assert storage.local_path == Path(temp_dir)
    
    def test_cns_fallback_configuration(self):
        """Test CNS fallback configuration integration"""
        storage = PathBasedStorage("cns://integration/test/path")
        assert storage.scheme == "file"  # Falls back to local
        assert "cns_fallback" in str(storage.local_path)
        assert storage.checkpoints_dir.exists()
        assert storage.metadata_dir.exists()
    
    def test_unsupported_scheme_error(self):
        """Test unsupported scheme error integration"""
        with pytest.raises(ValueError, match="Unsupported storage scheme"):
            PathBasedStorage("ftp://unsupported/path")


@pytest.mark.asyncio
async def test_full_system_integration():
    """Test complete system integration across all components"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create manager with realistic settings
        manager = EnhancedPersistenceManager(
            storage_path=temp_dir,
            auto_save_interval=20,
            max_checkpoints=10
        )
        
        # Test both GameBoy and DOS interfaces
        gameboy_interface = create_real_gameboy_interface()
        dos_interface = create_real_dos_interface()
        
        # Create checkpoints for both game types
        gameboy_checkpoint = await manager.save_checkpoint(
            game_interface=gameboy_interface,
            episode_id="full_integration_gameboy",
            step_number=50,
            action_history=[{"A": True}],
            observation_history=[{"screen": "gameboy_frame"}],
            reward_history=[1.0],
            metadata={"game_type": "gameboy"}
        )
        
        dos_checkpoint = await manager.save_checkpoint(
            game_interface=dos_interface,
            episode_id="full_integration_dos",
            step_number=75,
            action_history=[{"FIRE": True}],
            observation_history=[{"screen": "dos_frame"}],
            reward_history=[2.0],
            metadata={"game_type": "dos"}
        )
        
        # Verify both checkpoints were created
        assert gameboy_checkpoint is not None
        assert dos_checkpoint is not None
        
        # Test loading both checkpoints
        gameboy_result = await manager.load_checkpoint(gameboy_checkpoint, gameboy_interface)
        dos_result = await manager.load_checkpoint(dos_checkpoint, dos_interface)
        
        assert gameboy_result is not None
        assert dos_result is not None
        
        gameboy_state, gameboy_success = gameboy_result
        dos_state, dos_success = dos_result
        
        assert gameboy_success is True
        assert dos_success is True
        assert gameboy_state.game_type == "gameboy"
        assert dos_state.game_type == "dos"
        
        # Verify storage isolation
        gameboy_checkpoints = await manager.list_checkpoints("full_integration_gameboy")
        dos_checkpoints = await manager.list_checkpoints("full_integration_dos")
        
        assert len(gameboy_checkpoints) == 1
        assert len(dos_checkpoints) == 1
        assert gameboy_checkpoints[0]["checkpoint_id"] != dos_checkpoints[0]["checkpoint_id"] 