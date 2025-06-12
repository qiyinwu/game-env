"""
Docker Persistent Storage System
Provides persistent storage capabilities for game state checkpoints in Docker environments
"""

import asyncio
import pickle
import gzip
import json
import time
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse
import logging

from .game_state_persistence import (
    GameState, 
    GameStatePersistenceManager,
    GameBoyStateSaver,
    DOSStateSaver
)

# ============================================================================
# 1. Path-Based Storage System
# ============================================================================

class PathBasedStorage:
    """Unified path-based storage supporting local and CNS paths"""
    
    def __init__(self, storage_path: str):
        """Initialize storage with path-based configuration
        
        Supported paths:
        - Local paths: /path/to/storage or file:///path/to/storage
        - CNS paths: cns://path/to/storage (falls back to local temp)
        """
        self.storage_path = storage_path
        self.scheme, self.local_path = self._parse_storage_path(storage_path)
        
        # Initialize local storage directories
        self.checkpoints_dir = self.local_path / "checkpoints"
        self.metadata_dir = self.local_path / "metadata"
        self.index_file = self.metadata_dir / "checkpoint_index.json"
        
        # Create directories
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or create index
        self.index = self._load_index()
        
        # Ensure index file exists on disk
        if not self.index_file.exists():
            self._save_index()
        
        logging.info(f"PathBasedStorage initialized: {self.scheme}://{self.local_path}")
    
    def _parse_storage_path(self, path: str) -> Tuple[str, Path]:
        """Parse storage path and return scheme and local path"""
        if not path:
            raise ValueError("Storage path cannot be empty")
            
        if path.startswith(('/', '~', '.')):
            # Local absolute or relative path
            return "file", Path(path).expanduser().resolve()
        
        parsed = urlparse(path)
        scheme = parsed.scheme.lower()
        
        if not scheme or scheme == "file":
            # No scheme or file scheme - treat as local path
            if scheme == "file":
                return "file", Path(parsed.path)
            else:
                # No scheme, treat as local path
                return "file", Path(path).expanduser().resolve()
        elif scheme == "cns":
            # CNS fallback to local temporary directory
            temp_dir = Path(tempfile.gettempdir()) / "cns_fallback" / parsed.path.lstrip('/')
            temp_dir.mkdir(parents=True, exist_ok=True)
            logging.warning(f"CNS storage not implemented, using local fallback: {temp_dir}")
            return "file", temp_dir
        else:
            raise ValueError(f"Unsupported storage scheme: {scheme}")
    
    def _load_index(self) -> Dict[str, Any]:
        """Load checkpoint index"""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Failed to load index: {e}")
        
        return {"checkpoints": {}, "metadata": {"created_at": time.time()}}
    
    def _save_index(self):
        """Save checkpoint index"""
        try:
            # Make data JSON serializable
            serializable_index = self._make_json_serializable(self.index)
            with open(self.index_file, 'w') as f:
                json.dump(serializable_index, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save index: {e}")
    
    def _make_json_serializable(self, obj):
        """Convert bytes objects to base64 strings for JSON serialization"""
        if isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, (bytes, bytearray)):
            import base64
            return {"__bytes__": base64.b64encode(bytes(obj)).decode('ascii')}
        else:
            return obj
    
    def _restore_from_json(self, obj):
        """Restore bytes objects from JSON serialization"""
        if isinstance(obj, dict):
            if "__bytes__" in obj:
                import base64
                return base64.b64decode(obj["__bytes__"])
            return {k: self._restore_from_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._restore_from_json(item) for item in obj]
        else:
            return obj
    
    async def upload_checkpoint(self, checkpoint_id: str, data: bytes, metadata: Dict[str, Any]) -> bool:
        """Upload checkpoint to storage"""
        try:
            # Save checkpoint file
            checkpoint_file = self.checkpoints_dir / f"{checkpoint_id}.pkl.gz"
            with open(checkpoint_file, 'wb') as f:
                f.write(data)
            
            # Update index
            self.index["checkpoints"][checkpoint_id] = {
                "metadata": metadata,
                "file_path": str(checkpoint_file),
                "created_at": time.time(),
                "file_size": len(data)
            }
            
            self._save_index()
            return True
            
        except Exception as e:
            logging.error(f"Failed to upload checkpoint {checkpoint_id}: {e}")
            return False
    
    async def download_checkpoint(self, checkpoint_id: str) -> Optional[bytes]:
        """Download checkpoint from storage"""
        try:
            if checkpoint_id not in self.index["checkpoints"]:
                return None
            
            checkpoint_file = self.checkpoints_dir / f"{checkpoint_id}.pkl.gz"
            if not checkpoint_file.exists():
                return None
            
            with open(checkpoint_file, 'rb') as f:
                return f.read()
                
        except Exception as e:
            logging.error(f"Failed to download checkpoint {checkpoint_id}: {e}")
            return None
    
    async def list_checkpoints(self, episode_id: str = None) -> List[Dict[str, Any]]:
        """List available checkpoints"""
        checkpoints = []
        
        for checkpoint_id, info in self.index["checkpoints"].items():
            if episode_id is None or info["metadata"].get("episode_id") == episode_id:
                checkpoints.append({
                    "checkpoint_id": checkpoint_id,
                    "metadata": info["metadata"],
                    "created_at": info["created_at"],
                    "file_size": info["file_size"]
                })
        
        return sorted(checkpoints, key=lambda x: x["created_at"], reverse=True)
    
    async def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete checkpoint from storage"""
        try:
            if checkpoint_id not in self.index["checkpoints"]:
                return False
            
            # Delete file
            checkpoint_file = self.checkpoints_dir / f"{checkpoint_id}.pkl.gz"
            if checkpoint_file.exists():
                checkpoint_file.unlink()
            
            # Remove from index
            del self.index["checkpoints"][checkpoint_id]
            self._save_index()
            
            return True
            
        except Exception as e:
            logging.error(f"Failed to delete checkpoint {checkpoint_id}: {e}")
            return False

# ============================================================================
# 2. Enhanced Persistence Manager
# ============================================================================

class EnhancedPersistenceManager:
    """Enhanced persistence manager with path-based storage"""
    
    def __init__(self, 
                 storage_path: str,
                 auto_save_interval: int = 100,
                 max_checkpoints: int = 10):
        self.storage = PathBasedStorage(storage_path)
        self.auto_save_interval = auto_save_interval
        self.max_checkpoints = max_checkpoints
        
        # Game state savers
        self.savers = {
            "gameboy": GameBoyStateSaver(),
            "dos": DOSStateSaver()
        }
        
        logging.info(f"Enhanced persistence manager initialized")
    
    def _detect_game_type(self, game_interface) -> str:
        """Detect game type from interface"""
        if hasattr(game_interface, 'pyboy'):
            return "gameboy"
        elif hasattr(game_interface, 'browser'):
            return "dos"
        else:
            return "unknown"
    
    async def save_checkpoint(self,
                            game_interface,
                            episode_id: str,
                            step_number: int,
                            action_history: List[Any],
                            observation_history: List[Dict],
                            reward_history: List[float],
                            metadata: Dict = None) -> Optional[str]:
        """Save checkpoint using path-based storage"""
        try:
            # Detect game type and get saver
            game_type = self._detect_game_type(game_interface)
            saver = self.savers.get(game_type)
            
            if not saver:
                logging.error(f"No saver for game type: {game_type}")
                return None
            
            # Get screen data
            screen_data = b""
            if hasattr(game_interface, 'get_screen'):
                try:
                    screen_data = game_interface.get_screen()
                except Exception as e:
                    logging.warning(f"Failed to capture screen data: {e}, proceeding without screen data")
                    screen_data = b""  # Default to empty screen data
            
            # Save game state
            try:
                save_state = await saver.save_state(game_interface, metadata)
            except Exception as e:
                logging.warning(f"Failed to save full game state: {e}, using minimal state")
                save_state = {}  # Use empty state if saving fails
            
            # Get memory snapshot
            try:
                memory_snapshot = saver.get_memory_snapshot(game_interface)
            except Exception as e:
                logging.warning(f"Failed to get memory snapshot: {e}, using empty memory")
                memory_snapshot = {}  # Use empty memory if snapshot fails
            
            # Create game state
            game_state = GameState(
                game_type=game_type,
                game_name=getattr(game_interface, 'game_name', 'unknown'),
                episode_id=episode_id,
                step_number=step_number,
                timestamp=time.time(),
                screen_data=screen_data,
                game_memory=memory_snapshot,
                save_state=save_state,
                action_history=action_history.copy(),
                observation_history=observation_history.copy(),
                reward_history=reward_history.copy(),
                metadata=metadata or {}
            )
            
            # Generate checkpoint ID
            checkpoint_id = f"{episode_id}_step_{step_number}_{int(time.time())}"
            
            # Serialize and compress
            checkpoint_data = pickle.dumps(game_state)
            compressed_data = gzip.compress(checkpoint_data)
            
            # Upload to storage
            upload_metadata = {
                "episode_id": episode_id,
                "step_number": step_number,
                "game_type": game_type,
                "game_name": game_state.game_name,
                "timestamp": game_state.timestamp
            }
            
            success = await self.storage.upload_checkpoint(
                checkpoint_id, compressed_data, upload_metadata
            )
            
            if success:
                # Cleanup old checkpoints
                await self._cleanup_old_checkpoints(episode_id)
                logging.info(f"Saved checkpoint: {checkpoint_id}")
                return checkpoint_id
            
            return None
            
        except Exception as e:
            logging.error(f"Failed to save checkpoint: {e}")
            return None
    
    async def load_checkpoint(self, 
                            checkpoint_id: str,
                            game_interface) -> Optional[Tuple[GameState, bool]]:
        """Load checkpoint from path-based storage"""
        try:
            # Download checkpoint data
            compressed_data = await self.storage.download_checkpoint(checkpoint_id)
            if not compressed_data:
                return None
            
            # Decompress and deserialize
            checkpoint_data = gzip.decompress(compressed_data)
            game_state = pickle.loads(checkpoint_data)
            
            # Restore game state
            saver = self.savers.get(game_state.game_type)
            if saver and game_state.save_state:
                success = await saver.load_state(game_interface, game_state.save_state)
                return game_state, success
            else:
                return game_state, False
                
        except Exception as e:
            logging.error(f"Failed to load checkpoint {checkpoint_id}: {e}")
            return None
    
    async def list_checkpoints(self, episode_id: str = None) -> List[Dict[str, Any]]:
        """List checkpoints"""
        return await self.storage.list_checkpoints(episode_id)
    
    async def get_latest_checkpoint(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Get latest checkpoint for episode"""
        checkpoints = await self.list_checkpoints(episode_id)
        if checkpoints:
            return max(checkpoints, key=lambda x: x["metadata"]["step_number"])
        return None
    
    async def _cleanup_old_checkpoints(self, episode_id: str):
        """Clean up old checkpoints for episode"""
        checkpoints = await self.list_checkpoints(episode_id)
        
        if len(checkpoints) > self.max_checkpoints:
            # Sort by step number, keep latest
            sorted_checkpoints = sorted(
                checkpoints, 
                key=lambda x: x["metadata"]["step_number"], 
                reverse=True
            )
            
            # Delete old checkpoints
            for checkpoint in sorted_checkpoints[self.max_checkpoints:]:
                await self.storage.delete_checkpoint(checkpoint["checkpoint_id"])
                logging.info(f"Cleaned up old checkpoint: {checkpoint['checkpoint_id']}")

# ============================================================================
# 3. Configuration Generation
# ============================================================================

def create_docker_compose(storage_path: str = "/persistent_storage") -> str:
    """Create Docker Compose configuration"""
    return f"""version: '3.8'

services:
  videogamebench:
    build: .
    volumes:
      - persistent_storage:{storage_path}
    environment:
      - STORAGE_PATH={storage_path}
      - PYTHONPATH=/app
    working_dir: /app
    command: python -m src.persistence.docker_persistent_storage

volumes:
  persistent_storage:
    driver: local
"""

def create_storage_config(storage_type: str = "local", **kwargs) -> Dict[str, Any]:
    """Create storage configuration"""
    
    if storage_type == "local":
        return {
            "type": "local",
            "storage_path": kwargs.get("path", "/persistent_storage")
        }
    elif storage_type == "cns":
        return {
            "type": "cns",
            "storage_path": f"cns://{kwargs.get('path', '/cns/path')}"
        }
    else:
        # Default to local
        return {
            "type": "local",
            "storage_path": "/persistent_storage"
        }

# ============================================================================
# 4. Main Function for Testing
# ============================================================================

async def main():
    """Main function for testing"""
    import tempfile
    
    # Create temporary storage
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Using temporary storage: {temp_dir}")
        
        # Create manager
        manager = EnhancedPersistenceManager(
            storage_path=temp_dir,
            auto_save_interval=50,
            max_checkpoints=3
        )
        
        print("Enhanced persistence manager created successfully!")
        print(f"Storage scheme: {manager.storage.scheme}")
        print(f"Storage path: {manager.storage.local_path}")

if __name__ == "__main__":
    asyncio.run(main()) 