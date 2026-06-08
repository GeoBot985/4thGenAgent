# TaskFrame Runtime — Production Backend (on-prem pilot image)
#
# Builds a self-contained image that serves the controlled read/operate API
# (src.production_backend:app) via uvicorn. Live side effects remain blocked by
# the existing runtime guardrails; this image does NOT enable autonomous writes.
#
# Build:
#   docker build -t taskframe-runtime:pilot .
#   docker build --build-arg INSTALL_PDF=1 -t taskframe-runtime:pilot .   # + PDF/invoice extraction
#
# Run: see docker-compose.yml or docs/deployment_onprem.md.

FROM python:3.11-slim AS base

# INSTALL_PDF=1 pulls the optional PyMuPDF extra (needed only for PDF invoice extraction).
ARG INSTALL_PDF=0

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Source tree lives here; uvicorn is launched from /app so that
    # `src.*` / `runtime.*` imports and config/examples paths resolve correctly.
    PYTHONPATH=/app \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

WORKDIR /app

# Install dependencies first (better layer caching). Copy only packaging metadata,
# then install the declared dependencies without installing the package itself.
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip \
 && pip install "fastapi>=0.115,<1.0" "uvicorn[standard]>=0.34,<1.0" "pydantic>=2.7,<3.0" "pytz>=2024.1" \
 && if [ "$INSTALL_PDF" = "1" ]; then pip install "PyMuPDF>=1.24"; fi

# Copy the application source.
COPY src ./src
COPY runtime ./runtime
COPY tools ./tools
COPY tool_packs ./tool_packs
COPY config ./config
COPY docs ./docs
COPY manifests ./manifests
COPY pytest.ini ./pytest.ini

# Runtime state directory (audit, runs, stores). Mount a volume here in production
# so pilot data survives container restarts — see docker-compose.yml.
RUN mkdir -p /app/runtime_data

# Run as a non-root user.
RUN useradd --create-home --uid 10001 taskframe \
 && chown -R taskframe:taskframe /app
USER taskframe

EXPOSE 8000

# Liveness/readiness: the /health route requires a viewer-or-higher bearer token,
# so the healthcheck reuses TASKFRAME_BACKEND_VIEWER_TOKEN.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; \
req=urllib.request.Request(f'http://127.0.0.1:{os.environ.get(\"APP_PORT\",\"8000\")}/api/health', \
headers={'Authorization': 'Bearer '+os.environ.get('TASKFRAME_BACKEND_VIEWER_TOKEN','')}); \
exit(0 if urllib.request.urlopen(req, timeout=4).status==200 else 1)"

CMD ["sh", "-c", "uvicorn src.production_backend:app --host ${APP_HOST} --port ${APP_PORT} --workers ${APP_WORKERS:-2}"]
