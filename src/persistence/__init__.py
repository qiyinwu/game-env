"""
Persistence module for game state management
"""

from .game_state_persistence import (
    GameState,
    GameBoyStateSaver,
    DOSStateSaver,
    GameStatePersistenceManager,
    PersistentGameEnvironment
)

from .docker_persistent_storage import (
    PathBasedStorage,
    EnhancedPersistenceManager,
    create_docker_compose,
    create_storage_config
)

__all__ = [
    # Core persistence classes
    'GameState',
    'GameBoyStateSaver', 
    'DOSStateSaver',
    'GameStatePersistenceManager',
    'PersistentGameEnvironment',
    
    # Path-based storage
    'PathBasedStorage',
    'EnhancedPersistenceManager',
    
    # Utility functions
    'create_docker_compose',
    'create_storage_config'
]

__version__ = "1.0.0" 