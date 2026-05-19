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

ARG BUILD_DATE=unknown
ARG GIT_SHA=unknown
ARG GIT_REF=unknown

LABEL maintainer="Healthcare AI Team <ai@healthcare.internal>"
LABEL version="0.1.0"
LABEL description="AI-Assisted Prior Authorization Review Platform"
LABEL org.opencontainers.image.created="${BUILD_DATE}"
LABEL org.opencontainers.image.revision="${GIT_SHA}"
LABEL org.opencontainers.image.ref.name="${GIT_REF}"

WORKDIR /app

# Install minimal runtime OS deps
# libgl1 + libglib2.0-0 required by PaddleOCR (OpenCV)
# tesseract-ocr + poppler-utils required for local OCR fallback (pytesseract + pdf2image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security — never run as root in production
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source — owned by appuser
COPY --chown=appuser:appgroup . .

# Create upload directory with proper permissions
RUN mkdir -p /app/uploads /app/logs && chown -R appuser:appgroup /app/uploads /app/logs

# Make entrypoint executable
RUN chmod +x /app/docker/entrypoint.sh

# Switch to non-root user
USER appuser

# Expose application port
EXPOSE 8000

# Health check — polls the /health/live endpoint every 30s
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/live || exit 1

# Entrypoint: runs migrations then starts Gunicorn
ENTRYPOINT ["/bin/bash", "/app/docker/entrypoint.sh"]


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
