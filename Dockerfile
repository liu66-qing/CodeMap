FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project metadata first
COPY pyproject.toml README.md ./

# Copy source code
COPY src/ ./src/

# Install Python dependencies
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -e .

# Render Web Service port
EXPOSE 10000

# Start server
CMD ["sh", "-c", "uvicorn evograph.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
