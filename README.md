# Game Environment Library

A Python library for running AI agents on classic video games, supporting Game Boy and DOS games with comprehensive persistence, Docker deployment, and LLM integration.

> **Credits**: This project builds upon the excellent [VideoGameBench](https://github.com/alexzhang13/VideoGameBench) framework. We thank the original authors for their foundational work in game-based AI evaluation.

## Features ✨

- **🎮 Multi-Platform Support**: Game Boy (PyBoy) and DOS (JS-DOS) games
- **🤖 LLM Integration**: Works with any LiteLLM-compatible model (GPT, Claude, Gemini, etc.)
- **💾 Advanced Persistence**: Save/load game states with multiple storage backends
- **🐳 Docker Ready**: Full containerization with automatic setup
- **🔧 Server Mode**: REST API for external control
- **📊 Comprehensive Testing**: extensive tests with proper test pyramid structure (unit, integration, e2e)

## Quick Start 🚀

### Installation

```bash
# Create environment
conda create -n game-env python=3.10
conda activate game-env

# Install dependencies
pip install -r requirements.txt
playwright install  # For DOS games
```

### Basic Usage

```bash
# Test with fake actions (no API key needed)
python main.py --game pokemon_red --fake-actions --lite --max-steps 20

# Run with real LLM
python main.py --game pokemon_red --model gpt-4o --max-steps 50

# DOS games
python main.py --game doom --model gpt-4o --lite

# With UI
python main.py --game pokemon_red --fake-actions --enable-ui --lite
```

## Game State Persistence 💾

Advanced persistence system with multiple storage backends:

```python
from src.persistence import GameStatePersistenceManager

# Create persistence manager
manager = GameStatePersistenceManager(
    checkpoint_dir="./checkpoints",
    auto_save_interval=10,  # Save every 10 steps
    max_checkpoints=5
)

# Save checkpoint
checkpoint_id = await manager.save_checkpoint(
    game_interface=game,
    episode_id="my_episode",
    step_number=100,
    action_history=actions,
    observation_history=observations,
    reward_history=rewards
)

# Load checkpoint
result = await manager.load_checkpoint(checkpoint_id, game)
```

**Storage Backends:**
- Local filesystem
- AWS S3
- Google Cloud Storage
- Azure Blob Storage

## Docker Support 🐳

### Quick Start
```bash
# Build and run
docker build -t game-env .
./scripts/run-docker.sh

# With custom parameters
./scripts/run-docker.sh python main.py --game pokemon_red --fake-actions --max-steps 50
```

### Server Mode
```bash
# Start game server
python main.py --emulator gba --game pokemon_red --server-mode --headless --server-port 8080

# Control via REST API
curl -X POST http://localhost:8080/actions -H "Content-Type: application/json" -d '{"actions": ["A", "DOWN", "RIGHT"]}'
```

## ROM Setup 🎮

### Game Boy Games
```bash
# Create ROMs directory
mkdir -p roms

# Download legal Pokemon Red ROM
./scripts/download_roms.sh

# Or manually download
curl -L -o roms/pokemon_red.gb "https://github.com/x1qqDev/pokemon-red/raw/main/Pokemon.gb"
```

### DOS Games
DOS games are loaded automatically via JS-DOS - no ROM files needed.

## API Reference 📚

### REST API (Server Mode)

**Health Check**
```bash
curl http://localhost:8080/health
```

**Get Screenshots**
```bash
curl http://localhost:8080/screenshots?count=5
```

**Execute Actions**
```bash
curl -X POST http://localhost:8080/actions \
  -H "Content-Type: application/json" \
  -d '{"actions": ["A", "B", "START"]}'
```

**Reset Game**
```bash
curl -X POST http://localhost:8080/reset
```

### Python Client
```python
from examples.gba_client_example import GBAGameClient

client = GBAGameClient("http://localhost:8080")
screenshots = client.get_screenshots(count=3)
result = client.send_actions(["A", "DOWN", "A"])
```

## Supported Games 🎯

### Game Boy Games
- Pokemon Red
- Super Mario Land
- Kirby's Dream Land
- Mega Man: Dr. Wily's Revenge
- Donkey Kong Land 2
- Castlevania Adventure
- Scooby-Doo! Classic Creep Capers

### DOS Games
- Doom / Doom II
- Quake
- Warcraft II
- Civilization
- X-COM UFO Defense
- Prince of Persia
- Age of Empires

## Configuration ⚙️

Each game has its own config in `configs/{game}/`:
- `config.yaml` - Game settings
- `prompt.txt` - Game-specific LLM prompt
- `checkpoints/` - End-state detection images
- `preload.txt` - Pre-loaded actions (DOS games)

## Testing 🧪

Comprehensive test suite with 114 tests:

```bash
# Run all tests
pytest tests/ -v

# Run by category
pytest tests/ -m unit      # 55 unit tests
pytest tests/ -m integration  # 45 integration tests
pytest tests/ -m e2e --run-e2e  # 14 E2E tests
```

## Development 🛠️

### Project Structure
```
src/
├── persistence/          # Game state persistence
├── emulators/           # Game interfaces (GBA, DOS)
├── llm/                 # LLM integration
└── ui/                  # User interface

tests/
├── unit/               # Unit tests (mocked)
├── integration/        # Integration tests
└── e2e/               # End-to-end tests
```

### Adding New Games

1. **Game Boy**: Add ROM mapping to `src/consts.py`
2. **DOS**: Add game URL to `GAME_URL_MAP` in `src/consts.py`
3. **Config**: Create `configs/{game}/config.yaml`
4. **Prompt**: Add `configs/{game}/prompt.txt`

## Command Line Options 📋

```bash
# Common options
--game GAME              # Game to play
--model MODEL           # LLM model (LiteLLM format)
--lite                  # Pause game while model thinks
--max-steps N           # Maximum steps to run
--fake-actions          # Use random actions (no API key)
--enable-ui             # Show agent UI

# GBA specific
--server-mode           # Run as HTTP server
--server-port PORT      # Server port (default: 8080)
--headless              # No visual display

# DOS specific
--website-only          # Just open game website
```

## Credits & Dependencies 🙏

This project builds upon excellent open-source tools:

- **[VideoGameBench](https://github.com/alexzhang13/VideoGameBench)** - Original framework and inspiration
- **[PyBoy](https://github.com/Baekalfen/PyBoy)** - Game Boy emulator
- **[JS-DOS](https://js-dos.com/)** - DOS game emulation
- **[Playwright](https://playwright.dev/)** - Browser automation
- **[LiteLLM](https://docs.litellm.ai/)** - LLM API integration

## License 📄

MIT License - see [LICENSE](LICENSE) for details.

**Note**: Games are not covered by this license. Users must obtain proper licenses for any games they use.
