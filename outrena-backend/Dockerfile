# Dockerfile — OUTRENA backend (multi-stage build)
#
# Stage 1: builder — installs dependencies into a venv
# Stage 2: runtime — slim image, copies venv + app, runs gunicorn+uvicorn

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.8.5

# Build deps for asyncpg / cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy only manifests first — better layer caching
COPY pyproject.toml ./
COPY app/__init__.py ./app/__init__.py

# Install dependencies into a venv we can later copy
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install the project in editable mode WITHOUT the project sources
# (we'll mount/copy them later). Use --no-deps loop-hole: instead, just
# install all deps listed in pyproject.toml by parsing it.
RUN pip install --upgrade pip wheel setuptools \
    && pip install \
        "fastapi==0.115.6" \
        "uvicorn[standard]==0.34.0" \
        "gunicorn==23.0.0" \
        "starlette>=0.41.3" \
        "pydantic==2.10.4" \
        "pydantic-settings==2.7.1" \
        "email-validator==2.2.0" \
        "sqlalchemy[asyncio]==2.0.36" \
        "asyncpg==0.30.0" \
        "alembic==1.14.0" \
        "greenlet==3.1.1" \
        "redis[hiredis]==5.2.1" \
        "arq==0.26.1" \
        "python-jose[cryptography]==3.3.0" \
        "python-multipart==0.0.20" \
        "cryptography==44.0.0" \
        "httpx==0.28.1" \
        "apscheduler==3.11.0" \
        "structlog==24.4.0" \
        "rich==13.9.4" \
        "python-dotenv==1.0.1" \
        "tenacity==9.0.0" \
        "orjson==3.10.12" \
        "uvloop==0.21.0; sys_platform != 'win32'"

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    ENVIRONMENT=production

# Runtime libs for asyncpg / cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 outrena

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
WORKDIR /app
COPY --chown=outrena:outrena . /app

USER outrena

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Production: gunicorn with uvicorn workers. Override in dev compose for --reload.
CMD ["gunicorn", "app.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "4", \
     "-b", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--graceful-timeout", "30"]
