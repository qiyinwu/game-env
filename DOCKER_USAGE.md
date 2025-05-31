# Docker Usage Guide for VideoGameBench on gLinux

This guide explains how to build and run VideoGameBench using Docker on gLinux systems.

## Prerequisites

1. **Docker installed** on your gLinux system
2. **Docker Compose** (usually comes with Docker)
3. **X11 forwarding** enabled for GUI support (optional)

## Quick Start

### 1. Build the Docker Image

```bash
# Build the image
docker-compose build videogamebench

# Or build directly with Docker
docker build -t videogamebench .
```

### 2. Prepare ROM Files

```bash
# Create ROMs directory
mkdir -p roms

# Download Pokemon Red ROM (legal open-source version)
curl -L -o roms/pokemon_red.gb "https://github.com/pret/pokered/releases/download/symbols/pokered.gbc"
```

### 3. Run with Docker Compose

```bash
# Run fake actions test (no API key required)
docker-compose run --rm videogamebench python main.py --game pokemon_red --fake-actions --lite --max-steps 10

# Run with a real LLM (requires API key)
docker-compose run --rm -e OPENAI_API_KEY="your-api-key" videogamebench python main.py --game pokemon_red --model gpt-4o --lite --max-steps 20
```

## Detailed Usage

### Environment Variables

Set these environment variables for LLM API access:

```bash
# OpenAI
export OPENAI_API_KEY="your-openai-key"

# Anthropic
export ANTHROPIC_API_KEY="your-anthropic-key"

# Google (Gemini)
export GOOGLE_API_KEY="your-google-key"
```

### Running Different Games

```bash
# Game Boy games with fake actions
docker-compose run --rm videogamebench python main.py --game pokemon_red --fake-actions --lite --max-steps 20

# DOS games (no ROM required)
docker-compose run --rm -e OPENAI_API_KEY="$OPENAI_API_KEY" videogamebench python main.py --game doom --model gpt-4o --lite

# With UI support (requires X11 forwarding)
xhost +local:docker
docker-compose run --rm videogamebench python main.py --game pokemon_red --fake-actions --enable-ui --lite --max-steps 10
```

### Development Mode

For development with live code changes:

```bash
# Start development container
docker-compose run --rm videogamebench-dev

# Inside the container, you can run commands directly
python main.py --game pokemon_red --fake-actions --lite --max-steps 5
```

### Persistent Logs

Logs are automatically saved to the `./logs` directory on your host machine:

```bash
# View logs
ls -la logs/

# View specific game logs
ls -la logs/pokemon_red/fake_agent/
```

## Advanced Configuration

### Custom API Base (for Ollama, etc.)

```bash
# Run with custom API base
docker-compose run --rm videogamebench python main.py --game pokemon_red --model ollama/llama2 --api-base http://host.docker.internal:11434
```

### Volume Mounts

The Docker setup includes these volume mounts:

- `./roms:/app/roms:ro` - ROM files (read-only)
- `./logs:/app/logs` - Log output (read-write)
- `./configs:/app/configs:ro` - Game configurations (read-only)

### X11 GUI Support

For GUI applications on gLinux:

```bash
# Enable X11 forwarding
xhost +local:docker

# Run with GUI
docker-compose run --rm videogamebench python main.py --game pokemon_red --fake-actions --enable-ui --lite

# Disable X11 forwarding when done
xhost -local:docker
```

## Troubleshooting

### Common Issues

1. **Permission Denied for X11**
   ```bash
   xhost +local:docker
   ```

2. **ROM Files Not Found**
   ```bash
   # Ensure ROMs are in the correct directory
   ls -la roms/
   # Should show pokemon_red.gb and other ROM files
   ```

3. **API Key Not Working**
   ```bash
   # Check environment variables
   docker-compose run --rm videogamebench env | grep API_KEY
   ```

4. **Build Failures**
   ```bash
   # Clean build
   docker-compose build --no-cache videogamebench
   ```

### Performance Optimization

For better performance on gLinux:

```bash
# Use more CPU cores for building
docker-compose build --parallel videogamebench

# Limit memory usage if needed
docker-compose run --rm -m 2g videogamebench python main.py --game pokemon_red --fake-actions
```

## Example Commands

```bash
# Test installation
docker-compose run --rm videogamebench python main.py --help

# Quick fake actions test
docker-compose run --rm videogamebench python main.py --game pokemon_red --fake-actions --lite --max-steps 5

# Real LLM test with GPT-4
docker-compose run --rm -e OPENAI_API_KEY="$OPENAI_API_KEY" videogamebench python main.py --game pokemon_red --model gpt-4o --lite --max-steps 10

# DOS game with Gemini
docker-compose run --rm -e GOOGLE_API_KEY="$GOOGLE_API_KEY" videogamebench python main.py --game doom --model gemini/gemini-2.0-flash --lite

# Interactive development session
docker-compose run --rm videogamebench-dev
```

## Cleanup

```bash
# Remove containers
docker-compose down

# Remove images
docker rmi videogamebench

# Clean up everything
docker system prune -a
``` 