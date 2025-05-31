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
USER vgbench

# Copy requirements first for better Docker layer caching
COPY --chown=vgbench:vgbench requirements.txt .
COPY --chown=vgbench:vgbench setup.py .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Install the package in development mode
RUN pip install --no-cache-dir --user -e .

# Install Playwright browsers
RUN python -m playwright install chromium

# Copy the entire project
COPY --chown=vgbench:vgbench . .

# Create necessary directories
RUN mkdir -p roms logs configs

# Download Pokemon Red ROM (legal open-source version from pret project)
RUN curl -L -o roms/pokemon_red.gb "https://github.com/x1qqDev/pokemon-red/raw/main/Pokemon.gb" && \
    echo "Pokemon Red ROM downloaded successfully" && \
    ls -la roms/pokemon_red.gb

# Set up environment for the user's pip packages
ENV PATH="/home/vgbench/.local/bin:$PATH"

# Expose port for any web interfaces (if needed)
EXPOSE 8080

# Default command - can be overridden
CMD ["python", "main.py", "--game", "pokemon_red", "--fake-actions", "--lite", "--max-steps", "20"] 