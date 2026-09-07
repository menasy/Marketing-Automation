FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Create non-root system user and group (UID/GID 10001)
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -m appuser

WORKDIR /app

# Install system dependencies including curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and install Python dependencies
COPY pyproject.toml /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy application directories and output directory
COPY src/ /app/src/
COPY prompts/ /app/prompts/
COPY data/ /app/data/
COPY entrypoint-api.sh /app/entrypoint-api.sh
RUN mkdir -p /app/output && chmod 777 /app/output && \
    chmod +x /app/entrypoint-api.sh && \
    chown -R appuser:appuser /app

# Entrypoint runs as root to fix bind-mount permissions, then execs uvicorn

# Expose FastAPI application port
EXPOSE 8000

# Docker Healthcheck
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Command to execute FastAPI server via entrypoint (handles output dir permissions)
CMD ["/app/entrypoint-api.sh"]
