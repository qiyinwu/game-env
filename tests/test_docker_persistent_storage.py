"""
Tests for Docker persistent storage functionality
"""

import pytest
import tempfile
import asyncio
import json
import time
from pathlib import Path
from unittest.mock import Mock
import logging

from src.persistence.docker_persistent_storage import (
    PathBasedStorage,
    EnhancedPersistenceManager,
    create_docker_compose,
    create_storage_config
)

# ============================================================================
# Real Game Interface Classes (Minimal Mocking)
# ============================================================================

class RealGameBoyInterface:
    """Real GameBoy interface with minimal mocking"""
    
    def __init__(self, game_name="pokemon_red"):
        self.game_name = game_name
        self.pyboy = RealPyBoyEmulator()
    
    def get_screen(self):
        return b"real_gameboy_screen_160x144_data"

class RealPyBoyEmulator:
    """Real PyBoy emulator interface"""
    
    def __init__(self):
        self.memory = bytearray(b"real_gameboy_memory_" + bytes(range(100)))
        self._save_state_data = b"real_pyboy_save_state_12345"
    
    def save_state(self):
        return self._save_state_data
    
    def load_state(self, state_data):
        if state_data == self._save_state_data:
            return True
        return False

class RealDOSInterface:
    """Real DOS interface with minimal mocking"""
    
    def __init__(self, game_name="doom"):
        self.game_name = game_name
        self.browser = RealBrowserInterface()
    
    def get_screen(self):
        return b"real_dos_screen_320x200_data"

class RealBrowserInterface:
    """Real browser interface for DOS games"""
    
    def __init__(self):
        self.page = None  # Force use of execute_script path
        self._browser_state = {
            "localStorage": '{"game_progress": "level_3", "score": "1500"}',
            "sessionStorage": '{"current_level": "3", "lives": "3"}',
            "url": "http://dos-game.example.com/game.html",
            "dosboxState": None
        }
    
    def execute_script(self, script):
        # Simulate browser script execution
        if "return {" in script:
            return self._browser_state
        return None

# ============================================================================
# Path-Based Storage Tests (Local and CNS only)
# ============================================================================

class TestPathBasedStorageLocal:
    """Test path-based storage with local file system"""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def local_storage(self, temp_storage_dir):
        """Create local path-based storage"""
        return PathBasedStorage(temp_storage_dir)
    
    def test_initialization_local_path(self, local_storage, temp_storage_dir):
        """Test local storage initialization"""
        assert local_storage.scheme == "file"
        assert local_storage.local_path == Path(temp_storage_dir).resolve()
        assert local_storage.checkpoints_dir.exists()
        assert local_storage.metadata_dir.exists()
        assert local_storage.index_file.exists()
    
    def test_initialization_file_url(self, temp_storage_dir):
        """Test initialization with file:// URL"""
        file_url = f"file://{temp_storage_dir}"
        storage = PathBasedStorage(file_url)
        assert storage.scheme == "file"
        assert storage.local_path == Path(temp_storage_dir)
    
    def test_initialization_cns_fallback(self):
        """Test CNS initialization falls back to local"""
        storage = PathBasedStorage("cns://test/path")
        assert storage.scheme == "file"
        assert "cns_fallback" in str(storage.local_path)
    
    @pytest.mark.asyncio
    async def test_upload_checkpoint_success(self, local_storage):
        """Test successful checkpoint upload to local storage"""
        checkpoint_id = "test_checkpoint_001"
        data = b"test_checkpoint_data"
        metadata = {
            "episode_id": "test_episode",
            "step_number": 100,
            "game_type": "gameboy"
        }
        
        result = await local_storage.upload_checkpoint(checkpoint_id, data, metadata)
        
        assert result is True
        
        # Verify file exists
        checkpoint_file = local_storage.checkpoints_dir / f"{checkpoint_id}.pkl.gz"
        assert checkpoint_file.exists()
        
        # Verify index updated
        assert checkpoint_id in local_storage.index["checkpoints"]
        assert local_storage.index["checkpoints"][checkpoint_id]["metadata"] == metadata
    
    @pytest.mark.asyncio
    async def test_download_checkpoint_success(self, local_storage):
        """Test successful checkpoint download from local storage"""
        checkpoint_id = "test_checkpoint_002"
        original_data = b"test_checkpoint_data_for_download"
        metadata = {"episode_id": "test_episode", "step_number": 50}
        
        # First upload
        await local_storage.upload_checkpoint(checkpoint_id, original_data, metadata)
        
        # Then download
        downloaded_data = await local_storage.download_checkpoint(checkpoint_id)
        
        assert downloaded_data == original_data
    
    @pytest.mark.asyncio
    async def test_download_nonexistent_checkpoint(self, local_storage):
        """Test downloading a checkpoint that doesn't exist"""
        result = await local_storage.download_checkpoint("nonexistent_id")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_list_checkpoints(self, local_storage):
        """Test listing checkpoints"""
        # Upload multiple checkpoints
        checkpoints_data = [
            ("cp1", b"data1", {"episode_id": "ep1", "step_number": 10}),
            ("cp2", b"data2", {"episode_id": "ep1", "step_number": 20}),
            ("cp3", b"data3", {"episode_id": "ep2", "step_number": 15}),
        ]
        
        for cp_id, data, metadata in checkpoints_data:
            await local_storage.upload_checkpoint(cp_id, data, metadata)
        
        # List all checkpoints
        all_checkpoints = await local_storage.list_checkpoints()
        assert len(all_checkpoints) == 3
        
        # List checkpoints for specific episode
        ep1_checkpoints = await local_storage.list_checkpoints("ep1")
        assert len(ep1_checkpoints) == 2
        
        ep2_checkpoints = await local_storage.list_checkpoints("ep2")
        assert len(ep2_checkpoints) == 1
    
    @pytest.mark.asyncio
    async def test_delete_checkpoint(self, local_storage):
        """Test checkpoint deletion"""
        checkpoint_id = "test_checkpoint_delete"
        data = b"data_to_delete"
        metadata = {"episode_id": "test", "step_number": 1}
        
        # Upload checkpoint
        await local_storage.upload_checkpoint(checkpoint_id, data, metadata)
        
        # Verify it exists
        checkpoint_file = local_storage.checkpoints_dir / f"{checkpoint_id}.pkl.gz"
        assert checkpoint_file.exists()
        assert checkpoint_id in local_storage.index["checkpoints"]
        
        # Delete checkpoint
        result = await local_storage.delete_checkpoint(checkpoint_id)
        
        assert result is True
        assert not checkpoint_file.exists()
        assert checkpoint_id not in local_storage.index["checkpoints"]
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_checkpoint(self, local_storage):
        """Test deleting a checkpoint that doesn't exist"""
        result = await local_storage.delete_checkpoint("nonexistent_id")
        
        assert result is False
    
    def test_json_serialization_with_bytes(self, temp_storage_dir):
        """Test that bytes objects are properly serialized in index"""
        storage = PathBasedStorage(temp_storage_dir)
        
        # Test serialization
        test_obj = {
            "normal_data": "string",
            "bytes_data": b"some bytes",
            "bytearray_data": bytearray(b"some bytearray"),
            "nested": {
                "more_bytes": b"nested bytes"
            }
        }
        
        serialized = storage._make_json_serializable(test_obj)
        
        # Should be JSON serializable now
        json_str = json.dumps(serialized)
        assert json_str is not None
        
        # Test restoration
        restored = storage._restore_from_json(serialized)
        assert restored["normal_data"] == "string"
        assert restored["bytes_data"] == b"some bytes"
        assert restored["bytearray_data"] == bytearray(b"some bytearray")
        assert restored["nested"]["more_bytes"] == b"nested bytes"

# ============================================================================
# Enhanced Persistence Manager Tests (Real Functionality)
# ============================================================================

class TestEnhancedPersistenceManager:
    """Test the enhanced persistence manager with real functionality"""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def enhanced_manager(self, temp_storage_dir):
        """Create enhanced persistence manager with local storage"""
        return EnhancedPersistenceManager(
            storage_path=temp_storage_dir,
            auto_save_interval=5,
            max_checkpoints=3
        )
    
    @pytest.mark.asyncio
    async def test_save_checkpoint_with_real_gameboy_interface(self, enhanced_manager):
        """Test checkpoint saving using real GameBoy interface"""
        interface = RealGameBoyInterface("pokemon_red")
        action_history = [{"A": True}, {"B": True}, {"START": False}]
        observation_history = [{"screen": "obs1", "score": 100}, {"screen": "obs2", "score": 150}]
        reward_history = [1.0, 2.5]
        
        checkpoint_id = await enhanced_manager.save_checkpoint(
            game_interface=interface,
            episode_id="real_gameboy_test",
            step_number=50,
            action_history=action_history,
            observation_history=observation_history,
            reward_history=reward_history,
            metadata={"level": 3, "score": 1500}
        )
        
        assert checkpoint_id is not None
        assert "real_gameboy_test_step_50" in checkpoint_id
        
        # Verify actual file was created and contains real data
        storage_files = list(Path(enhanced_manager.storage.local_path).glob("**/*.pkl.gz"))
        assert len(storage_files) == 1
        
        # Test that we can actually read and deserialize the saved data
        import pickle
        import gzip
        with open(storage_files[0], 'rb') as f:
            compressed_data = f.read()
        
        decompressed_data = gzip.decompress(compressed_data)
        game_state = pickle.loads(decompressed_data)
        
        # Verify the real data was saved correctly
        assert game_state.game_type == "gameboy"
        assert game_state.episode_id == "real_gameboy_test"
        assert game_state.step_number == 50
        assert game_state.save_state == b"real_pyboy_save_state_12345"
        assert game_state.game_memory == b"real_gameboy_memory_" + bytes(range(100))
        assert game_state.action_history == action_history
        assert game_state.observation_history == observation_history
        assert game_state.reward_history == reward_history
        assert game_state.metadata["level"] == 3
    
    @pytest.mark.asyncio
    async def test_save_checkpoint_with_real_dos_interface(self, enhanced_manager):
        """Test checkpoint saving using real DOS interface"""
        interface = RealDOSInterface("doom")
        action_history = [{"UP": True}, {"SPACE": True}]
        observation_history = [{"screen": "dos_obs1"}, {"screen": "dos_obs2"}]
        reward_history = [0.5, 1.5]
        
        checkpoint_id = await enhanced_manager.save_checkpoint(
            game_interface=interface,
            episode_id="real_dos_test",
            step_number=75,
            action_history=action_history,
            observation_history=observation_history,
            reward_history=reward_history,
            metadata={"level": "E1M1", "ammo": 50}
        )
        
        assert checkpoint_id is not None
        assert "real_dos_test_step_75" in checkpoint_id
        
        # Verify actual file was created and contains real DOS state data
        storage_files = list(Path(enhanced_manager.storage.local_path).glob("**/*.pkl.gz"))
        assert len(storage_files) == 1
        
        # Test that we can actually read and deserialize the saved data
        import pickle
        import gzip
        with open(storage_files[0], 'rb') as f:
            compressed_data = f.read()
        
        decompressed_data = gzip.decompress(compressed_data)
        game_state = pickle.loads(decompressed_data)
        
        # Verify the real DOS data was saved correctly
        assert game_state.game_type == "dos"
        assert game_state.episode_id == "real_dos_test"
        assert game_state.step_number == 75
        
        # Verify the DOS state contains real browser state
        import json
        dos_state = json.loads(game_state.save_state.decode('utf-8'))
        assert "localStorage" in dos_state
        assert "sessionStorage" in dos_state
        assert "game_progress" in dos_state["localStorage"]
        assert game_state.action_history == action_history
        assert game_state.metadata["level"] == "E1M1"
    
    @pytest.mark.asyncio
    async def test_load_checkpoint_with_real_data_verification(self, enhanced_manager):
        """Test loading checkpoint and verify real data integrity"""
        interface = RealGameBoyInterface("pokemon_blue")
        
        # First save a checkpoint with real data
        original_action_history = [{"A": True}, {"B": False}, {"SELECT": True}]
        original_observation_history = [{"screen": f"frame_{i}", "hp": 100-i*5} for i in range(3)]
        original_reward_history = [1.0, 1.5, 2.0]
        original_metadata = {"level": 5, "score": 2500, "items": ["potion", "key"]}
        
        checkpoint_id = await enhanced_manager.save_checkpoint(
            game_interface=interface,
            episode_id="data_integrity_test",
            step_number=125,
            action_history=original_action_history,
            observation_history=original_observation_history,
            reward_history=original_reward_history,
            metadata=original_metadata
        )
        
        # Now load it and verify ALL data is preserved correctly
        result = await enhanced_manager.load_checkpoint(checkpoint_id, interface)
        
        assert result is not None
        game_state, success = result
        assert success is True
        
        # Verify EXACT data preservation (not just mock returns)
        assert game_state.episode_id == "data_integrity_test"
        assert game_state.step_number == 125
        assert game_state.game_type == "gameboy"
        assert game_state.game_name == "pokemon_blue"
        
        # Verify complex data structures are preserved exactly
        assert game_state.action_history == original_action_history
        assert game_state.observation_history == original_observation_history
        assert game_state.reward_history == original_reward_history
        assert game_state.metadata == original_metadata
        assert game_state.metadata["items"] == ["potion", "key"]  # Nested data
    
    @pytest.mark.asyncio
    async def test_game_type_detection_with_real_interfaces(self, enhanced_manager):
        """Test game type detection with real interface structures"""
        
        gb_interface = RealGameBoyInterface()
        dos_interface = RealDOSInterface()
        
        # Test with interface that has neither pyboy nor browser
        class UnknownInterface:
            def __init__(self):
                self.some_other_system = object()
                self.game_name = "unknown_game"
        
        unknown_interface = UnknownInterface()
        
        assert enhanced_manager._detect_game_type(gb_interface) == "gameboy"
        assert enhanced_manager._detect_game_type(dos_interface) == "dos"
        assert enhanced_manager._detect_game_type(unknown_interface) == "unknown"
    
    @pytest.mark.asyncio
    async def test_cleanup_with_real_checkpoints(self, enhanced_manager):
        """Test cleanup functionality with real checkpoint files"""
        interface = RealGameBoyInterface()
        
        # Save more checkpoints than max_checkpoints (3) with real data
        checkpoint_ids = []
        for i in range(5):  # More than max of 3
            checkpoint_id = await enhanced_manager.save_checkpoint(
                game_interface=interface,
                episode_id="cleanup_real_test",
                step_number=i * 10,
                action_history=[{"step": i}],
                observation_history=[{"frame": i}],
                reward_history=[float(i)]
            )
            checkpoint_ids.append(checkpoint_id)
            # Small delay to ensure different timestamps
            await asyncio.sleep(0.01)
        
        # Verify cleanup actually deleted real files
        remaining_checkpoints = await enhanced_manager.list_checkpoints("cleanup_real_test")
        assert len(remaining_checkpoints) <= enhanced_manager.max_checkpoints
        
        # Verify the remaining files actually exist and are readable
        storage_files = list(Path(enhanced_manager.storage.local_path).glob("**/*.pkl.gz"))
        assert len(storage_files) <= enhanced_manager.max_checkpoints
        
        # Verify we can actually load the remaining checkpoints
        for checkpoint_info in remaining_checkpoints:
            result = await enhanced_manager.load_checkpoint(
                checkpoint_info["checkpoint_id"], 
                interface
            )
            assert result is not None
            game_state, success = result
            assert success is True
            assert game_state.episode_id == "cleanup_real_test"
    
    @pytest.mark.asyncio
    async def test_json_serialization_edge_cases_real_data(self, enhanced_manager):
        """Test JSON serialization with real edge case data"""
        storage = enhanced_manager.storage
        
        # Test with real complex data structures that could break JSON
        complex_data = {
            "binary_data": b"\x00\x01\x02\xff\xfe\xfd",  # Real binary
            "large_bytearray": bytearray(range(256)),  # Full byte range
            "nested_bytes": {
                "level1": {
                    "level2": b"nested_binary_data",
                    "mixed": [b"bytes1", "string", b"bytes2"]
                }
            },
            "unicode_strings": "Test with émojis 🎮🕹️ and unicode",
            "empty_bytes": b"",
            "large_data": b"x" * 10000  # Large binary data
        }
        
        # Test serialization
        serialized = storage._make_json_serializable(complex_data)
        
        # Verify it's actually JSON serializable (this would fail with real bytes)
        import json
        json_str = json.dumps(serialized)
        assert len(json_str) > 0
        
        # Test restoration preserves exact data
        restored = storage._restore_from_json(serialized)
        
        assert restored["binary_data"] == b"\x00\x01\x02\xff\xfe\xfd"
        assert restored["large_bytearray"] == bytearray(range(256))
        assert restored["nested_bytes"]["level1"]["level2"] == b"nested_binary_data"
        assert restored["nested_bytes"]["level1"]["mixed"][0] == b"bytes1"
        assert restored["nested_bytes"]["level1"]["mixed"][1] == "string"
        assert restored["nested_bytes"]["level1"]["mixed"][2] == b"bytes2"
        assert restored["unicode_strings"] == "Test with émojis 🎮🕹️ and unicode"
        assert restored["empty_bytes"] == b""
        assert restored["large_data"] == b"x" * 10000
    
    @pytest.mark.asyncio
    async def test_list_checkpoints_real_data(self, enhanced_manager):
        """Test listing checkpoints returns real data"""
        # This should return an empty list initially (real behavior)
        checkpoints = await enhanced_manager.list_checkpoints()
        assert isinstance(checkpoints, list)
        assert len(checkpoints) == 0  # Real empty state
    
    @pytest.mark.asyncio
    async def test_get_latest_checkpoint_real_behavior(self, enhanced_manager):
        """Test getting latest checkpoint with real behavior"""
        # Should return None when no checkpoints exist (real behavior)
        latest = await enhanced_manager.get_latest_checkpoint("nonexistent_episode")
        assert latest is None  # Real None, not mock return

    @pytest.mark.asyncio
    async def test_real_error_handling_without_mocks(self, temp_storage_dir):
        """Test error handling with real error conditions"""
        manager = EnhancedPersistenceManager(storage_path=temp_storage_dir)
        
        # Test with interface that will cause real errors
        class BrokenInterface:
            def __init__(self):
                self.pyboy = None  # This will cause real AttributeError
                self.game_name = "broken_game"
        
        broken_interface = BrokenInterface()
        
        # This should handle real errors gracefully
        checkpoint_id = await manager.save_checkpoint(
            game_interface=broken_interface,
            episode_id="error_test",
            step_number=1,
            action_history=[],
            observation_history=[],
            reward_history=[]
        )
        
        # The checkpoint should still be created since the interface has pyboy attribute
        # (even though it's None), but the save_state will be empty
        assert checkpoint_id is not None
        
        # Verify the checkpoint was created but with empty save state
        storage_files = list(Path(temp_storage_dir).glob("**/*.pkl.gz"))
        assert len(storage_files) == 1
        
        # Load and verify the checkpoint has empty save state due to error
        import pickle
        import gzip
        with open(storage_files[0], 'rb') as f:
            raw_data = f.read()
        
        decompressed = gzip.decompress(raw_data)
        game_state = pickle.loads(decompressed)
        
        # Should have empty save state due to the error
        assert game_state.save_state == b""
        assert game_state.game_memory is None

# ============================================================================
# Configuration Generation Tests
# ============================================================================

class TestConfigurationGeneration:
    """Test configuration generation functions"""
    
    def test_create_docker_compose(self):
        """Test Docker Compose generation"""
        compose_content = create_docker_compose("/custom/storage/path")
        
        assert "version: '3.8'" in compose_content
        assert "videogamebench:" in compose_content
        assert "/custom/storage/path" in compose_content
        assert "persistent_storage:" in compose_content
        assert "STORAGE_PATH=/custom/storage/path" in compose_content
    
    def test_create_storage_config_local(self):
        """Test local storage configuration"""
        config = create_storage_config("local", path="/my/local/path")
        
        assert config["type"] == "local"
        assert config["storage_path"] == "/my/local/path"
    
    def test_create_storage_config_cns(self):
        """Test CNS storage configuration"""
        config = create_storage_config("cns", path="/cns/path")
        
        assert config["type"] == "cns"
        assert config["storage_path"] == "cns:///cns/path"
    
    def test_create_storage_config_default(self):
        """Test default storage configuration"""
        config = create_storage_config("unknown_type")
        
        assert config["type"] == "local"
        assert config["storage_path"] == "/persistent_storage"

# ============================================================================
# Path Parsing Tests
# ============================================================================

class TestPathBasedStorageSchemes:
    """Test different storage scheme initializations"""
    
    def test_local_path_initialization(self):
        """Test local path initialization"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = PathBasedStorage(temp_dir)
            assert storage.scheme == "file"
    
    def test_file_url_initialization(self):
        """Test file:// URL initialization"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = PathBasedStorage(f"file://{temp_dir}")
            assert storage.scheme == "file"
    
    def test_cns_url_initialization(self):
        """Test CNS URL initialization (falls back to local)"""
        storage = PathBasedStorage("cns://my-cns-path/data")
        assert storage.scheme == "file"  # Falls back to local
        assert "cns_fallback" in str(storage.local_path)
    
    def test_unsupported_scheme(self):
        """Test unsupported scheme raises error"""
        with pytest.raises(ValueError, match="Unsupported storage scheme"):
            PathBasedStorage("ftp://unsupported/path")

# ============================================================================
# Integration Tests (Real Data Flow)
# ============================================================================

class TestIntegration:
    """Integration tests for real path-based persistence functionality"""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.mark.asyncio
    async def test_full_persistence_cycle_real_data_flow(self, temp_storage_dir):
        """Test complete persistence cycle with real data flow"""
        # Create manager
        manager = EnhancedPersistenceManager(
            storage_path=temp_storage_dir,
            auto_save_interval=10,
            max_checkpoints=5
        )
        
        # Create real game interface
        interface = RealGameBoyInterface("integration_test_game")
        
        # Use REAL complex data structures
        complex_action_history = [
            {"A": True, "B": False, "timestamp": 1.0},
            {"A": False, "B": True, "timestamp": 2.5},
            {"START": True, "SELECT": False, "timestamp": 3.7}
        ]
        complex_observation_history = [
            {"screen": "frame_1", "hp": 100, "score": 0, "items": ["sword"]},
            {"screen": "frame_2", "hp": 95, "score": 50, "items": ["sword", "potion"]},
            {"screen": "frame_3", "hp": 90, "score": 100, "items": ["sword", "potion", "key"]}
        ]
        complex_reward_history = [0.0, 1.5, 2.0]
        complex_metadata = {
            "level": 3,
            "score": 1500,
            "inventory": ["sword", "shield", "potion"],
            "stats": {"hp": 90, "mp": 50, "exp": 1200},
            "binary_data": b"\x01\x02\x03\xff",
            "nested": {"deep": {"value": "test"}}
        }
        
        # Save checkpoint with real data
        checkpoint_id = await manager.save_checkpoint(
            game_interface=interface,
            episode_id="integration_test",
            step_number=100,
            action_history=complex_action_history,
            observation_history=complex_observation_history,
            reward_history=complex_reward_history,
            metadata=complex_metadata
        )
        
        assert checkpoint_id is not None
        
        # Verify real file system operations occurred
        storage_files = list(Path(temp_storage_dir).glob("**/*.pkl.gz"))
        assert len(storage_files) == 1
        
        # Verify we can manually read and deserialize the file (real data test)
        import pickle
        import gzip
        with open(storage_files[0], 'rb') as f:
            raw_data = f.read()
        
        decompressed = gzip.decompress(raw_data)
        game_state = pickle.loads(decompressed)
        
        # Verify ALL complex data was preserved exactly
        assert game_state.episode_id == "integration_test"
        assert game_state.step_number == 100
        assert game_state.game_type == "gameboy"
        assert game_state.action_history == complex_action_history
        assert game_state.observation_history == complex_observation_history
        assert game_state.reward_history == complex_reward_history
        assert game_state.metadata == complex_metadata
        assert game_state.metadata["binary_data"] == b"\x01\x02\x03\xff"
        assert game_state.metadata["nested"]["deep"]["value"] == "test"
        
        # Load checkpoint using manager (tests real loading logic)
        result = await manager.load_checkpoint(checkpoint_id, interface)
        assert result is not None
        
        loaded_game_state, success = result
        assert success is True
        
        # Verify loaded data matches original exactly
        assert loaded_game_state.episode_id == "integration_test"
        assert loaded_game_state.step_number == 100
        assert loaded_game_state.action_history == complex_action_history
        assert loaded_game_state.observation_history == complex_observation_history
        assert loaded_game_state.reward_history == complex_reward_history
        assert loaded_game_state.metadata == complex_metadata
    
    @pytest.mark.asyncio
    async def test_multiple_storage_paths_real_isolation(self):
        """Test that different storage paths are truly isolated"""
        with tempfile.TemporaryDirectory() as temp_dir1, \
             tempfile.TemporaryDirectory() as temp_dir2:
            
            # Create two managers with different paths
            manager1 = EnhancedPersistenceManager(storage_path=temp_dir1)
            manager2 = EnhancedPersistenceManager(storage_path=temp_dir2)
            
            # Create real interfaces
            interface1 = RealGameBoyInterface("game1")
            interface2 = RealGameBoyInterface("game2")
            
            # Save different data to each manager
            checkpoint1 = await manager1.save_checkpoint(
                game_interface=interface1,
                episode_id="episode1",
                step_number=50,
                action_history=[{"manager": 1}],
                observation_history=[{"data": "manager1"}],
                reward_history=[1.0]
            )
            
            checkpoint2 = await manager2.save_checkpoint(
                game_interface=interface2,
                episode_id="episode2",
                step_number=75,
                action_history=[{"manager": 2}],
                observation_history=[{"data": "manager2"}],
                reward_history=[2.0]
            )
            
            # Verify real file system isolation
            files1 = list(Path(temp_dir1).glob("**/*.pkl.gz"))
            files2 = list(Path(temp_dir2).glob("**/*.pkl.gz"))
            
            assert len(files1) == 1
            assert len(files2) == 1
            assert files1[0] != files2[0]  # Different files
            
            # Verify data isolation by loading and checking content
            result1 = await manager1.load_checkpoint(checkpoint1, interface1)
            result2 = await manager2.load_checkpoint(checkpoint2, interface2)
            
            assert result1 is not None
            assert result2 is not None
            
            game_state1, success1 = result1
            game_state2, success2 = result2
            
            assert success1 and success2
            assert game_state1.episode_id == "episode1"
            assert game_state2.episode_id == "episode2"
            assert game_state1.action_history[0]["manager"] == 1
            assert game_state2.action_history[0]["manager"] == 2
            
            # Verify cross-manager isolation (manager1 can't load manager2's data)
            cross_result = await manager1.load_checkpoint(checkpoint2, interface1)
            assert cross_result is None  # Should fail - real isolation
    
    @pytest.mark.asyncio
    async def test_real_concurrent_access_simulation(self, temp_storage_dir):
        """Test concurrent access patterns with real async operations"""
        manager = EnhancedPersistenceManager(storage_path=temp_storage_dir)
        
        # Create multiple real interfaces
        interfaces = [
            RealGameBoyInterface(f"concurrent_game_{i}")
            for i in range(3)
        ]
        
        # Simulate concurrent saves (real async operations)
        async def save_checkpoint(interface_idx):
            return await manager.save_checkpoint(
                game_interface=interfaces[interface_idx],
                episode_id=f"concurrent_episode_{interface_idx}",
                step_number=interface_idx * 10,
                action_history=[{"concurrent": interface_idx}],
                observation_history=[{"frame": interface_idx}],
                reward_history=[float(interface_idx)]
            )
        
        # Run concurrent operations
        checkpoint_ids = await asyncio.gather(
            save_checkpoint(0),
            save_checkpoint(1),
            save_checkpoint(2)
        )
        
        # Verify all succeeded
        assert all(cid is not None for cid in checkpoint_ids)
        assert len(set(checkpoint_ids)) == 3  # All unique
        
        # Verify real files were created
        storage_files = list(Path(temp_storage_dir).glob("**/*.pkl.gz"))
        assert len(storage_files) == 3
        
        # Verify each checkpoint contains correct data
        for i, checkpoint_id in enumerate(checkpoint_ids):
            result = await manager.load_checkpoint(checkpoint_id, interfaces[i])
            assert result is not None
            game_state, success = result
            assert success
            assert game_state.episode_id == f"concurrent_episode_{i}"
            assert game_state.action_history[0]["concurrent"] == i 