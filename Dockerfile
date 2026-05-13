# ============================================================
# PA Review Platform — Multi-Stage Production Dockerfile
# Stage 1: builder  — installs all deps into /install
# Stage 2: production — minimal runtime image, non-root user
# ============================================================

# ---- Stage 1: Builder ----
FROM python:3.11-slim AS builder

WORKDIR /build

# Install system build tools required by some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libssl-dev \
    libffi-dev \
    libglib2.0-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install pip tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy dependency manifests first (layer caching — only re-installs if deps change)
COPY requirements.txt .

# Install all production dependencies into an isolated prefix
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ---- Stage 2: Production ----
FROM python:3.11-slim AS production

LABEL maintainer="Healthcare AI Team <ai@healthcare.internal>"
LABEL version="0.1.0"
LABEL description="AI-Assisted Prior Authorization Review Platform"

WORKDIR /app

# Install minimal runtime OS deps
# libgl1-mesa-glx + libglib2.0-0 are required by PaddleOCR (OpenCV)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security — never run as root in production
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source — owned by appuser
COPY --chown=appuser:appgroup . .

# Create upload directory with proper permissions
RUN mkdir -p /app/uploads /app/logs && chown -R appuser:appgroup /app/uploads /app/logs

# Switch to non-root user
USER appuser

# Expose application port
EXPOSE 8000

# Health check — polls the /health endpoint every 30s
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Default command — override with Gunicorn in production orchestration
# Single worker here; Kubernetes handles horizontal scaling
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--loop", "uvloop", \
     "--log-config", "/dev/null"]


# ---- Stage 3: Development (optional override) ----
FROM production AS development

USER root

RUN pip install --no-cache-dir \
    pytest pytest-asyncio pytest-cov pytest-mock \
    httpx factory-boy faker locust ruff mypy black

USER appuser

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--reload", \
     "--log-config", "/dev/null"]
