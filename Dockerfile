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
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 vgbench && \
    chown -R vgbench:vgbench /app

# CORRECTED: Create persistent storage directories AS ROOT and give ownership to vgbench
RUN mkdir -p /persistent_storage/checkpoints \
    && mkdir -p /persistent_storage/metadata \
    && chown -R vgbench:vgbench /persistent_storage

# CORRECTED: Switch to the non-root user AFTER all root-level setup is complete
USER vgbench

# Copy requirements first for better Docker layer caching
COPY --chown=vgbench:vgbench requirements.txt .
COPY --chown=vgbench:vgbench setup.py .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Install additional persistent storage dependencies
RUN pip install --no-cache-dir --user \
    boto3 \
    google-cloud-storage \
    azure-storage-blob \
    pyyaml

# CORRECTED: Copy the entire project context BEFORE installing it
COPY --chown=vgbench:vgbench . .

# CORRECTED: Install the package in development mode (this will now find the 'src' directory)
RUN pip install --no-cache-dir --user -e .

# Install Playwright browsers
RUN python -m playwright install chromium

# Copy and set up entrypoint script
COPY --chown=vgbench:vgbench scripts/docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# Create necessary directories including persistent storage
RUN mkdir -p roms logs configs \
    && mkdir -p /persistent_storage/checkpoints \
    && mkdir -p /persistent_storage/metadata

# Download Pokemon Red ROM (legal open-source version from pret project)
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

# Expose port for any web interfaces (if needed)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Set entrypoint to our custom script
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default command - can be overridden
CMD []