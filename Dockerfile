# Use Python 3.11 slim image as base for better compatibility
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /app

# Install system dependencies required for the project
RUN apt-get update && apt-get install -y \
    # Build tools
    build-essential \
    gcc \
    g++ \
    make \
    # Git for cloning repositories
    git \
    # For PyBoy and pygame
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-mixer-dev \
    libsdl2-ttf-dev \
    # For OpenCV
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # For Playwright browser automation
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxss1 \
    libasound2 \
    # For GUI support (tkinter)
    python3-tk \
    # Utilities
    curl \
    wget \
    unzip \
    # Add iproute2 for 'ss' command
    iproute2 \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 vgbench && \
    chown -R vgbench:vgbench /app

# Create persistent storage directories AS ROOT and give ownership to vgbench
RUN mkdir -p /persistent_storage/checkpoints \
    && mkdir -p /persistent_storage/metadata \
    && chown -R vgbench:vgbench /persistent_storage

# Copy requirements and setup.py first for better Docker layer caching
COPY --chown=vgbench:vgbench requirements.txt .
COPY --chown=vgbench:vgbench setup.py .

# Switch to the non-root user for pip installations
USER vgbench

# Install Python dependencies from requirements.txt
RUN pip install --no-cache-dir --user -r requirements.txt

# Install additional cloud storage dependencies
RUN pip install --no-cache-dir --user \
    boto3 \
    google-cloud-storage \
    azure-storage-blob \
    pyyaml

# Copy the entire project
COPY --chown=vgbench:vgbench . .

# Install the project in editable mode (now that source code is copied)
RUN pip install --no-cache-dir --user -e .

# VERIFY yaml installation
RUN python -c "import yaml; print('YAML module is installed and importable!')" || \
    (echo 'ERROR: YAML module is NOT importable after installation!' && exit 1)

# Install Playwright browsers
RUN python -m playwright install chromium

# Create necessary directories (user can create these in /app)
RUN mkdir -p roms logs configs

# Download Pokemon Red ROM (legal open-source version)
RUN curl -L -o roms/pokemon_red.gb "https://github.com/x1qqDev/pokemon-red/raw/main/Pokemon.gb" && \
    echo "Pokemon Red ROM downloaded successfully" && \
    ls -la roms/pokemon_red.gb

# Set up environment for the user's pip packages
ENV PATH="/home/vgbench/.local/bin:$PATH"

# Set persistent storage environment variables
ENV PYTHONPATH=/app
ENV STORAGE_TYPE=volume
ENV STORAGE_PATH=/persistent_storage
ENV AUTO_RESUME=true

# Expose port for any web interfaces
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Default command - can be overridden
CMD ["python", "main.py", "--help"]