# Official lightweight Python 3.10 slim runtime
FROM python:3.10-slim

# Prevent python from buffering stdout/stderr & bytecode generation
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=10000

# Install system dependencies: ffmpeg for Edge-TTS audio synthesis & curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency definition and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire application and ecosystem
COPY . .

# Expose the application port
EXPOSE 10000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/health || exit 1

# Start the continuous voice agent via Uvicorn
CMD ["sh", "-c", "uvicorn run:app --host 0.0.0.0 --port ${PORT}"]
