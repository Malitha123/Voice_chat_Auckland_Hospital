# =============================================================================
# Auckland Hospital Health Assistant - API container
#
# Two stages:
#
#   1. builder — installs CPU-only PyTorch (saves ~700 MB vs the default CUDA
#      build) plus the rest of requirements.txt into a venv.
#   2. runtime — slim image with the venv copied in, no build tools, no apt
#      cache. Runs ``uvicorn api.main:app`` on port 8000.
#
# Deliberately omitted: ``playwright install chromium`` — the optional crawler
# MCP would pull ~600 MB of Chromium binaries. The Python ``playwright``
# package is still installed (importing it is fine without browsers); the
# crawler tool requires a browser-enabled build when invoked. Set
# ``--build-arg WITH_PLAYWRIGHT=true`` for deployments that enable crawling.
# =============================================================================

# Frontend build. The compiled React/Vite SPA is bundled into the API image so
# the browser application and API can share one origin.
FROM node:20-slim AS webbuilder
WORKDIR /web
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ ./
# In production the SPA talks to the backend over relative /api/* paths
# (same origin), so no VITE_API_URL is needed at build time.
RUN npm run build          # → /web/dist


# Dependency build
FROM python:3.13-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build-time native deps (psycopg2 needs libpq + a C compiler at install time).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Keep Python dependencies in a virtual environment copied into the runtime stage.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build

# Pre-install CPU-only torch first. sentence-transformers depends on torch;
# resolving it later would otherwise pull the full CUDA wheel (~2 GB).
RUN pip install --upgrade pip wheel \
 && pip install --index-url https://download.pytorch.org/whl/cpu \
        torch torchvision torchaudio

COPY requirements.txt ./
RUN pip install -r requirements.txt


# Runtime image
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PATH="/opt/venv/bin:$PATH" \
    HF_HOME=/root/.cache/huggingface \
    TRANSFORMERS_CACHE=/root/.cache/huggingface/transformers \
    SENTENCE_TRANSFORMERS_HOME=/root/.cache/huggingface/sentence_transformers \
    LANGFUSE_PROMPTS=false

# Runtime needs only libpq (psycopg2 client) and curl (healthcheck).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy the prebuilt venv from the builder.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Application runtime code and configuration only. Database schema and seed files
# are applied separately and are not required by the running API process.
COPY src    ./src
COPY config ./config

# The compiled SPA from Frontend build. FastAPI serves it at / (see api/main.py:
# StaticFiles mount + /api path-strip middleware). Lives at /app/ui_dist so
# main.py can resolve it as parents[2]/ui_dist relative to src/api/main.py.
COPY --from=webbuilder /web/dist ./ui_dist

# Quick liveness check; lifespan warmup can take 30-60 s on a cold start
# while the local sentence-transformers model loads, so give it a buffer.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
