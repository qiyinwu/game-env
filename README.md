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

### Environment Variables

Set up API keys for LLM providers:

```bash
# OpenAI
export OPENAI_API_KEY="your-openai-key"

# Anthropic Claude
export ANTHROPIC_API_KEY="your-anthropic-key"

# Google Gemini
export GOOGLE_API_KEY="your-google-key"
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

## Complete Example 🎯

Here's a full end-to-end example of running Pokemon Red with Docker:

```bash
# 1. Set up environment
export OPENAI_API_KEY="your-actual-api-key"

# 2. Build Docker image
docker compose build

# 3. Test with fake actions first
docker compose run --rm game-env python main.py --game pokemon_red --fake-actions --lite --max-steps 5

# 4. Run server mode in background
docker compose run --rm -p 8080:8080 game-env python main.py --emulator gba --game pokemon_red --server-mode --headless --server-port 8080 &

# 5. Test the API (in another terminal)
curl http://localhost:8080/health
curl http://localhost:8080/status
curl -X POST http://localhost:8080/actions -H "Content-Type: application/json" -d '{"actions": ["A", "START"]}'
curl http://localhost:8080/screenshots

# 6. Run with real LLM
docker compose run --rm -e OPENAI_API_KEY="$OPENAI_API_KEY" game-env python main.py --game pokemon_red --model gpt-4o --lite --max-steps 10
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

### Using Docker Compose (Recommended)

```bash
# Build the image
docker compose build

# Run with help
docker compose run --rm game-env

# Test with fake actions
docker compose run --rm game-env python main.py --game pokemon_red --fake-actions --lite --max-steps 10

# Run with real LLM (set API key first)
docker compose run --rm -e OPENAI_API_KEY="your-key" game-env python main.py --game pokemon_red --model gpt-4o --lite --max-steps 20

# Interactive development mode
docker compose run --rm game-env bash
```

### Server Mode

```bash
# Start game server
docker compose run --rm -p 8080:8080 game-env python main.py --emulator gba --game pokemon_red --server-mode --headless --server-port 8080

# Or using native Python
python main.py --emulator gba --game pokemon_red --server-mode --headless --server-port 8080

# Control via REST API
curl -X POST http://localhost:8080/actions -H "Content-Type: application/json" -d '{"actions": ["A", "DOWN", "RIGHT"]}'
```

### Alternative: Direct Docker Build

```bash
# Build and run with scripts
docker build -t game-env .
./scripts/run-docker.sh python main.py --game pokemon_red --fake-actions --max-steps 50
```

> **Note**: You may see warnings like "Deprecated use of headless" from PyBoy and "Read-only file system" errors. These are normal and don't affect functionality - the ROM directory is intentionally mounted read-only for security.

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
# Response: {"status": "healthy", "server": "gba_game_server"}
```

**Game Status**
```bash
curl http://localhost:8080/status
# Response: {"state": "playing", "step": 5, "running": true, "screenshot_history_count": 6}
```

**Get Screenshots**
```bash
# Get latest screenshot
curl http://localhost:8080/screenshots

# Get multiple recent screenshots
curl http://localhost:8080/screenshots?count=5
# Response: {"screenshots": [...], "count": 5, "current_step": 10, "format": "base64_png"}
```

**Execute Actions**
```bash
# Single action
curl -X POST http://localhost:8080/actions \
  -H "Content-Type: application/json" \
  -d '{"actions": ["A"]}'

# Multiple actions
curl -X POST http://localhost:8080/actions \
  -H "Content-Type: application/json" \
  -d '{"actions": ["A", "B", "START", "DOWN", "RIGHT"]}'

# Response: {"success": true, "total_actions": 3, "results": [...], "final_step": 8}
```

**Reset Game**
```bash
curl -X POST http://localhost:8080/reset
# Response: {"success": true, "message": "Game reset"}
```

**Available Game Actions:**
- Game Boy: `A`, `B`, `START`, `SELECT`, `UP`, `DOWN`, `LEFT`, `RIGHT`

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
