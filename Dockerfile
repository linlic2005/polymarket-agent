# ============================================================
# Polymarket Agent - Production Dockerfile
# Multi-stage: builder + runtime
# ============================================================

# ---------- Stage 1: Builder ----------
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (cache layer)
COPY pyproject.toml ./
RUN pip install --no-cache-dir --prefix=/install -e .[dev]

# ---------- Stage 2: Runtime ----------
FROM python:3.11-slim AS runtime

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 polygroup \
    && useradd --uid 1000 --gid polygroup --shell /bin/bash --create-home polyuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY --chown=polyuser:polygroup . .

# Switch to non-root user
USER polyuser

# Environment defaults (can be overridden at runtime)
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production
ENV PYTHONPATH=/app

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run
CMD ["uvicorn", "apps.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
