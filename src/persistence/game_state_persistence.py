"""
Game State Persistence System
Game state persistence system - for recovering game progress after sampler crashes
"""

import asyncio
import pickle
import json
import hashlib
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import numpy as np
from PIL import Image
import logging

# ============================================================================
# 1. Game State Data Structures
# ============================================================================

@dataclass
class GameState:
    """Game state snapshot"""
    # Basic information
    game_type: str                    # "gameboy" or "dos"
    game_name: str                    # Game name
    episode_id: str                   # Episode ID
    step_number: int                  # Current step number
    timestamp: float                  # Timestamp
    
    # Game state
    screen_data: bytes                # Screenshot data
    game_memory: Optional[bytes]      # Game memory state (if supported)
    save_state: Optional[bytes]       # Emulator save state
    
    # History information
    action_history: List[Any]         # Action history
    observation_history: List[Dict]   # Observation history
    reward_history: List[float]       # Reward history
    
    # Metadata
    metadata: Dict[str, Any]          # Additional metadata

@dataclass
class CheckpointInfo:
    """Checkpoint information"""
    checkpoint_id: str
    game_state: GameState
    file_path: Path
    created_at: float
    file_size: int
    checksum: str

# ============================================================================
# 2. Game State Saver Base Class
# ============================================================================

class GameStateSaver(ABC):
    """Game state saver abstract base class"""
    
    @abstractmethod
    async def save_state(self, game_interface, additional_data: Dict = None) -> bytes:
        """Save game state"""
        pass
    
    @abstractmethod
    async def load_state(self, game_interface, state_data: bytes) -> bool:
        """Load game state"""
        pass
    
    @abstractmethod
    def get_memory_snapshot(self, game_interface) -> Optional[bytes]:
        """Get memory snapshot"""
        pass

class GameBoyStateSaver(GameStateSaver):
    """Game Boy game state saver"""
    
    async def save_state(self, game_interface, additional_data: Dict = None) -> bytes:
        """Save Game Boy game state"""
        try:
            # PyBoy supports save state
            if hasattr(game_interface.pyboy, 'save_state'):
                # Save to memory
                state_data = game_interface.pyboy.save_state()
                return state_data
            else:
                # If not supported, save memory snapshot
                return self.get_memory_snapshot(game_interface) or b""
        except Exception as e:
            logging.error(f"Failed to save Game Boy state: {e}")
            # Try fallback to memory snapshot
            try:
                memory_snapshot = self.get_memory_snapshot(game_interface)
                return memory_snapshot or b""
            except Exception:
                return b""
    
    async def load_state(self, game_interface, state_data: bytes) -> bool:
        """Load Game Boy game state"""
        try:
            if hasattr(game_interface.pyboy, 'load_state') and state_data:
                game_interface.pyboy.load_state(state_data)
                return True
            return False
        except Exception as e:
            logging.error(f"Failed to load Game Boy state: {e}")
            return False
    
    def get_memory_snapshot(self, game_interface) -> Optional[bytes]:
        """Get Game Boy memory snapshot"""
        try:
            # Get game memory state
            if hasattr(game_interface.pyboy, 'memory'):
                memory_data = bytes(game_interface.pyboy.memory)
                return memory_data
            return None
        except Exception as e:
            logging.error(f"Failed to get Game Boy memory snapshot: {e}")
            return None

class DOSStateSaver(GameStateSaver):
    """DOS game state saver"""
    
    async def save_state(self, game_interface, additional_data: Dict = None) -> bytes:
        """Save DOS game state"""
        try:
            # DOS game runs through browser, save page state
            if hasattr(game_interface.browser, 'page') and game_interface.browser.page is not None:
                # Get page state (localStorage, sessionStorage, etc.)
                page_state = await game_interface.browser.page.evaluate("""
                () => {
                    return {
                        localStorage: JSON.stringify(localStorage),
                        sessionStorage: JSON.stringify(sessionStorage),
                        url: window.location.href,
                        dosboxState: window.dosbox ? window.dosbox.getState() : null
                    };
                }
                """)
                
                return json.dumps(page_state).encode('utf-8')
            elif hasattr(game_interface.browser, 'execute_script'):
                # Alternative interface using execute_script
                script_result = game_interface.browser.execute_script("""
                return {
                    localStorage: JSON.stringify(localStorage),
                    sessionStorage: JSON.stringify(sessionStorage),
                    url: window.location.href,
                    dosboxState: window.dosbox ? window.dosbox.getState() : null
                };
                """)
                
                if isinstance(script_result, str):
                    # If result is already JSON string
                    page_state = json.loads(script_result)
                else:
                    # If result is object
                    page_state = script_result
                
                return json.dumps(page_state).encode('utf-8')
            return b""
        except Exception as e:
            logging.error(f"Failed to save DOS state: {e}")
            return b""
    
    async def load_state(self, game_interface, state_data: bytes) -> bool:
        """Load DOS game state"""
        try:
            if state_data:
                page_state = json.loads(state_data.decode('utf-8'))
                
                if hasattr(game_interface.browser, 'page') and game_interface.browser.page is not None:
                    # Restore page state using page.evaluate
                    await game_interface.browser.page.evaluate(f"""
                    (pageState) => {{
                        // Restore localStorage
                        if (pageState.localStorage) {{
                            const localStorage_data = JSON.parse(pageState.localStorage);
                            for (const [key, value] of Object.entries(localStorage_data)) {{
                                localStorage.setItem(key, value);
                            }}
                        }}
                        
                        // Restore sessionStorage
                        if (pageState.sessionStorage) {{
                            const sessionStorage_data = JSON.parse(pageState.sessionStorage);
                            for (const [key, value] of Object.entries(sessionStorage_data)) {{
                                sessionStorage.setItem(key, value);
                            }}
                        }}
                        
                        // Restore DOS emulator state
                        if (pageState.dosboxState && window.dosbox) {{
                            window.dosbox.setState(pageState.dosboxState);
                        }}
                    }}
                    """, page_state)
                elif hasattr(game_interface.browser, 'execute_script'):
                    # Restore using execute_script
                    # Restore localStorage
                    if 'localStorage' in page_state and page_state['localStorage']:
                        localStorage_data = json.loads(page_state['localStorage'])
                        for key, value in localStorage_data.items():
                            game_interface.browser.execute_script(
                                f"localStorage.setItem('{key}', '{value}');"
                            )
                    
                    # Restore sessionStorage
                    if 'sessionStorage' in page_state and page_state['sessionStorage']:
                        sessionStorage_data = json.loads(page_state['sessionStorage'])
                        for key, value in sessionStorage_data.items():
                            game_interface.browser.execute_script(
                                f"sessionStorage.setItem('{key}', '{value}');"
                            )
                
                return True
            return False
        except Exception as e:
            logging.error(f"Failed to load DOS state: {e}")
            return False
    
    def get_memory_snapshot(self, game_interface) -> Optional[bytes]:
        """DOS game memory snapshot (limited support)"""
        return None

# ============================================================================
# 3. Persistence Manager
# ============================================================================

class GameStatePersistenceManager:
    """Game state persistence manager"""
    
    def __init__(self, 
                 checkpoint_dir: Path,
                 auto_save_interval: int = 100,  # Save every 100 steps
                 max_checkpoints: int = 10,      # Keep up to 10 checkpoints
                 compression: bool = True):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.auto_save_interval = auto_save_interval
        self.max_checkpoints = max_checkpoints
        self.compression = compression
        
        # Game type to saver mapping
        self.savers = {
            "gameboy": GameBoyStateSaver(),
            "dos": DOSStateSaver()
        }
        
        # Checkpoint index
        self.checkpoints: List[CheckpointInfo] = []
        self._load_checkpoint_index()
        
        logging.info(f"Persistence manager initialized. Checkpoint dir: {checkpoint_dir}")
    
    def _load_checkpoint_index(self):
        """Load checkpoint index"""
        index_file = self.checkpoint_dir / "checkpoint_index.json"
        if index_file.exists():
            try:
                with open(index_file, 'r') as f:
                    data = json.load(f)
                    
                self.checkpoints = []
                for item in data:
                    # Reconstruct GameState with minimal data (full data loaded from file when needed)
                    game_state = GameState(
                        game_type=item['game_state']['game_type'],
                        game_name=item['game_state']['game_name'],
                        episode_id=item['game_state']['episode_id'],
                        step_number=item['game_state']['step_number'],
                        timestamp=item['game_state']['timestamp'],
                        screen_data=b"",  # Will be loaded from file when needed
                        game_memory=None,  # Will be loaded from file when needed
                        save_state=None,  # Will be loaded from file when needed
                        action_history=[],  # Will be loaded from file when needed
                        observation_history=[],  # Will be loaded from file when needed
                        reward_history=[],  # Will be loaded from file when needed
                        metadata=item['game_state']['metadata']
                    )
                    
                    checkpoint_info = CheckpointInfo(
                        checkpoint_id=item['checkpoint_id'],
                        game_state=game_state,
                        file_path=Path(item['file_path']),
                        created_at=item['created_at'],
                        file_size=item['file_size'],
                        checksum=item['checksum']
                    )
                    self.checkpoints.append(checkpoint_info)
                    
                logging.info(f"Loaded {len(self.checkpoints)} checkpoints from index")
            except Exception as e:
                logging.error(f"Failed to load checkpoint index: {e}")
                self.checkpoints = []
    
    def _save_checkpoint_index(self):
        """Save checkpoint index"""
        index_file = self.checkpoint_dir / "checkpoint_index.json"
        try:
            data = []
            for cp in self.checkpoints:
                # Convert CheckpointInfo to dict, handling nested GameState
                cp_dict = {
                    'checkpoint_id': cp.checkpoint_id,
                    'file_path': str(cp.file_path),
                    'created_at': cp.created_at,
                    'file_size': cp.file_size,
                    'checksum': cp.checksum,
                    'game_state': {
                        'game_type': cp.game_state.game_type,
                        'game_name': cp.game_state.game_name,
                        'episode_id': cp.game_state.episode_id,
                        'step_number': cp.game_state.step_number,
                        'timestamp': cp.game_state.timestamp,
                        'metadata': cp.game_state.metadata
                        # Note: We don't save bytes fields (screen_data, game_memory, save_state)
                        # and history data in the index for performance reasons
                    }
                }
                data.append(cp_dict)
            
            with open(index_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save checkpoint index: {e}")
    
    def _generate_checkpoint_id(self, episode_id: str, step: int) -> str:
        """Generate checkpoint ID"""
        timestamp = int(time.time())
        return f"{episode_id}_step_{step}_{timestamp}"
    
    def _calculate_checksum(self, data: bytes) -> str:
        """Calculate data checksum"""
        return hashlib.md5(data).hexdigest()
    
    async def save_checkpoint(self, 
                            game_interface,
                            episode_id: str,
                            step_number: int,
                            action_history: List[Any],
                            observation_history: List[Dict],
                            reward_history: List[float],
                            metadata: Dict = None) -> Optional[str]:
        """Save game checkpoint"""
        
        try:
            # Determine game type
            game_type = self._detect_game_type(game_interface)
            saver = self.savers.get(game_type)
            
            if not saver:
                logging.error(f"No saver available for game type: {game_type}")
                return None
            
            # Get current screen
            screen_image = None
            if hasattr(game_interface, 'get_screen'):
                screen_image = game_interface.get_screen()
            elif hasattr(game_interface, 'get_observation'):
                obs = await game_interface.get_observation()
                if isinstance(obs, dict) and 'screen' in obs:
                    screen_image = obs['screen']
                else:
                    screen_image = obs
            
            # Convert screen data
            screen_data = b""
            if screen_image:
                if isinstance(screen_image, Image.Image):
                    import io
                    buffer = io.BytesIO()
                    screen_image.save(buffer, format='PNG')
                    screen_data = buffer.getvalue()
                elif isinstance(screen_image, bytes):
                    screen_data = screen_image
            
            # Save game state
            save_state = await saver.save_state(game_interface, metadata)
            
            # Create game state object
            game_state = GameState(
                game_type=game_type,
                game_name=getattr(game_interface, 'game_name', 'unknown'),
                episode_id=episode_id,
                step_number=step_number,
                timestamp=time.time(),
                screen_data=screen_data,
                game_memory=saver.get_memory_snapshot(game_interface),
                save_state=save_state,
                action_history=action_history.copy(),
                observation_history=observation_history.copy(),
                reward_history=reward_history.copy(),
                metadata=metadata or {}
            )
            
            # Generate checkpoint ID and file path
            checkpoint_id = self._generate_checkpoint_id(episode_id, step_number)
            checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.pkl"
            
            # Serialize and save
            checkpoint_data = pickle.dumps(game_state)
            
            # Optional compression
            if self.compression:
                import gzip
                checkpoint_data = gzip.compress(checkpoint_data)
                checkpoint_file = checkpoint_file.with_suffix('.pkl.gz')
            
            with open(checkpoint_file, 'wb') as f:
                f.write(checkpoint_data)
            
            # Create checkpoint info
            checkpoint_info = CheckpointInfo(
                checkpoint_id=checkpoint_id,
                game_state=game_state,
                file_path=checkpoint_file,
                created_at=time.time(),
                file_size=len(checkpoint_data),
                checksum=self._calculate_checksum(checkpoint_data)
            )
            
            # Add to index
            self.checkpoints.append(checkpoint_info)
            
            # Clean up old checkpoints
            self._cleanup_old_checkpoints()
            
            # Save index
            self._save_checkpoint_index()
            
            logging.info(f"Saved checkpoint {checkpoint_id} at step {step_number}")
            return checkpoint_id
            
        except Exception as e:
            logging.error(f"Failed to save checkpoint: {e}")
            return None
    
    async def load_checkpoint(self, 
                            checkpoint_id: str,
                            game_interface) -> Optional[Tuple[GameState, bool]]:
        """Load game checkpoint"""
        
        try:
            # Find checkpoint
            checkpoint_info = None
            for cp in self.checkpoints:
                if cp.checkpoint_id == checkpoint_id:
                    checkpoint_info = cp
                    break
            
            if not checkpoint_info:
                logging.error(f"Checkpoint {checkpoint_id} not found")
                return None
            
            # Read checkpoint file
            if not checkpoint_info.file_path.exists():
                logging.error(f"Checkpoint file not found: {checkpoint_info.file_path}")
                return None
            
            with open(checkpoint_info.file_path, 'rb') as f:
                checkpoint_data = f.read()
            
            # Verify checksum
            if self._calculate_checksum(checkpoint_data) != checkpoint_info.checksum:
                logging.error(f"Checkpoint {checkpoint_id} checksum mismatch")
                return None
            
            # Decompress
            if self.compression and checkpoint_info.file_path.suffix == '.gz':
                import gzip
                checkpoint_data = gzip.decompress(checkpoint_data)
            
            # Deserialize
            game_state = pickle.loads(checkpoint_data)
            
            # Restore game state
            saver = self.savers.get(game_state.game_type)
            if saver and game_state.save_state:
                success = await saver.load_state(game_interface, game_state.save_state)
                logging.info(f"Loaded checkpoint {checkpoint_id}, game state restored: {success}")
                return game_state, success
            else:
                logging.warning(f"Could not restore game state for {checkpoint_id}")
                return game_state, False
                
        except Exception as e:
            logging.error(f"Failed to load checkpoint {checkpoint_id}: {e}")
            return None
    
    def _detect_game_type(self, game_interface) -> str:
        """Detect game type"""
        if hasattr(game_interface, 'pyboy'):
            return "gameboy"
        elif hasattr(game_interface, 'browser'):
            return "dos"
        else:
            return "unknown"
    
    def _cleanup_old_checkpoints(self):
        """Clean up old checkpoints"""
        if len(self.checkpoints) > self.max_checkpoints:
            # Sort by time, remove oldest
            self.checkpoints.sort(key=lambda x: x.created_at)
            
            to_remove = self.checkpoints[:-self.max_checkpoints]
            for cp in to_remove:
                try:
                    if cp.file_path.exists():
                        cp.file_path.unlink()
                    logging.info(f"Removed old checkpoint: {cp.checkpoint_id}")
                except Exception as e:
                    logging.error(f"Failed to remove checkpoint {cp.checkpoint_id}: {e}")
            
            self.checkpoints = self.checkpoints[-self.max_checkpoints:]
    
    def list_checkpoints(self, episode_id: str = None) -> List[CheckpointInfo]:
        """List checkpoints"""
        if episode_id:
            return [cp for cp in self.checkpoints if cp.game_state.episode_id == episode_id]
        return self.checkpoints.copy()
    
    def get_latest_checkpoint(self, episode_id: str) -> Optional[CheckpointInfo]:
        """Get latest checkpoint"""
        episode_checkpoints = self.list_checkpoints(episode_id)
        if episode_checkpoints:
            return max(episode_checkpoints, key=lambda x: x.game_state.step_number)
        return None

# ============================================================================
# 4. Enhanced Environment Wrapper (Supports Automatic Saving)
# ============================================================================

class PersistentGameEnvironment:
    """Support persistent game environment wrapper"""
    
    def __init__(self, 
                 base_env,
                 persistence_manager: GameStatePersistenceManager,
                 episode_id: str = None):
        self.base_env = base_env
        self.persistence_manager = persistence_manager
        self.episode_id = episode_id or f"episode_{int(time.time())}"
        
        # History
        self.action_history = []
        self.observation_history = []
        self.reward_history = []
        
        # State
        self.step_count = 0
        self.last_checkpoint_step = 0
        
    async def reset(self, restore_from_checkpoint: str = None) -> Dict[str, Any]:
        """Reset environment, optionally restore from checkpoint"""
        
        if restore_from_checkpoint:
            # Restore from checkpoint
            result = await self.persistence_manager.load_checkpoint(
                restore_from_checkpoint, 
                self.base_env.game_interface
            )
            
            if result:
                game_state, success = result
                if success:
                    # Restore history
                    self.action_history = game_state.action_history.copy()
                    self.observation_history = game_state.observation_history.copy()
                    self.reward_history = game_state.reward_history.copy()
                    self.step_count = game_state.step_number
                    self.episode_id = game_state.episode_id
                    
                    logging.info(f"Restored from checkpoint at step {self.step_count}")
                    
                    # Return current observation
                    current_obs = await self.base_env.get_observation()
                    return self.base_env._format_observation(current_obs)
        
        # Normal reset
        obs = await self.base_env.reset()
        self.action_history = []
        self.observation_history = [obs]
        self.reward_history = []
        self.step_count = 0
        self.last_checkpoint_step = 0
        
        return obs
    
    async def step(self, action: Any) -> Tuple[Dict[str, Any], float, bool, Dict[str, Any]]:
        """Execute step, automatically save checkpoint"""
        
        # Execute action
        obs, reward, done, info = await self.base_env.step(action)
        
        # Update history
        self.action_history.append(action)
        self.observation_history.append(obs)
        self.reward_history.append(reward)
        self.step_count += 1
        
        # Check if checkpoint needs to be saved
        if (self.step_count - self.last_checkpoint_step >= 
            self.persistence_manager.auto_save_interval):
            
            checkpoint_id = await self.persistence_manager.save_checkpoint(
                game_interface=self.base_env.game_interface,
                episode_id=self.episode_id,
                step_number=self.step_count,
                action_history=self.action_history,
                observation_history=self.observation_history,
                reward_history=self.reward_history,
                metadata={"done": done, "info": info}
            )
            
            if checkpoint_id:
                self.last_checkpoint_step = self.step_count
                info["checkpoint_saved"] = checkpoint_id
        
        return obs, reward, done, info
    
    async def save_checkpoint_now(self) -> Optional[str]:
        """Save checkpoint immediately"""
        return await self.persistence_manager.save_checkpoint(
            game_interface=self.base_env.game_interface,
            episode_id=self.episode_id,
            step_number=self.step_count,
            action_history=self.action_history,
            observation_history=self.observation_history,
            reward_history=self.reward_history
        )

# ============================================================================
# 5. Usage Example
# ============================================================================

async def example_usage():
    """Usage example"""
    
    # 1. Create persistence manager
    persistence_manager = GameStatePersistenceManager(
        checkpoint_dir=Path("./checkpoints"),
        auto_save_interval=50,  # Save every 50 steps
        max_checkpoints=5
    )
    
    # 2. Example with a mock game interface
    class MockGameInterface:
        def __init__(self):
            self.step_count = 0
        
        async def get_screen(self):
            return b"mock_screen_data"
        
        async def get_observation(self):
            return {"screen": "mock_observation", "step": self.step_count}
    
    # 3. Create mock environment
    game_interface = MockGameInterface()
    
    # 4. Create persistent environment
    persistent_env = PersistentGameEnvironment(
        base_env=game_interface,
        persistence_manager=persistence_manager,
        episode_id="pokemon_session_001"
    )
    
    try:
        # 5. Simulate game session
        action_history = []
        observation_history = []
        reward_history = []
        
        for step in range(100):
            # Simulate game step
            action = {"A": True}  # Mock action
            observation = await game_interface.get_observation()
            reward = 1.0  # Mock reward
            
            action_history.append(action)
            observation_history.append(observation)
            reward_history.append(reward)
            
            # Save checkpoint every 50 steps
            if step % 50 == 0:
                checkpoint_id = await persistence_manager.save_checkpoint(
                    game_interface=game_interface,
                    episode_id="pokemon_session_001",
                    step_number=step,
                    action_history=action_history,
                    observation_history=observation_history,
                    reward_history=reward_history
                )
                if checkpoint_id:
                    print(f"Checkpoint saved: {checkpoint_id}")
                
    except Exception as e:
        print(f"Session crashed at step {step}: {e}")
        
        # 6. Restore from latest checkpoint
        latest_checkpoint = persistence_manager.get_latest_checkpoint("pokemon_session_001")
        if latest_checkpoint:
            print(f"Restoring from checkpoint: {latest_checkpoint.checkpoint_id}")
            result = await persistence_manager.load_checkpoint(
                latest_checkpoint.checkpoint_id, 
                game_interface
            )
            if result:
                game_state, success = result
                print(f"Resumed session from step {game_state.step_number}")

if __name__ == "__main__":
    asyncio.run(example_usage()) 