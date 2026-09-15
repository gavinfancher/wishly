
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.12 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app/backend

# Layer 1: dependencies only (cached unless the lockfile changes). --no-install-project
# skips building wishly itself so this layer is independent of source changes.
#
# One image, one container. There used to be a second (`--group worker`) holding
# Prefect for the send pipeline; the send is now an endpoint on this API, started
# by an EventBridge rule, so orchestration/ imports nothing extra. A
# scale-to-zero Fargate task re-pulls this image on every cold start, so the
# 106 MB that left with Prefect is recovery time saved.
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Layer 2: project source, then install the project (no dev deps in the image).
COPY backend/ ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---- runtime: minimal image carrying only the venv + source ------------------
FROM python:3.12-slim AS runtime

# Non-root runtime user.
RUN groupadd --system app && useradd --system --gid app --create-home app

ENV PATH="/app/backend/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app/backend
COPY --from=builder --chown=app:app /app/backend /app/backend

USER app
EXPOSE 8000

# Load config from Secrets Manager (if WISHLY_SECRETS_ID is set), then exec.
ENTRYPOINT ["python", "-m", "wishly.bootstrap"]


# Liveness against the in-process /health route (curl is not in the slim image).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"]

CMD ["uvicorn", "wishly.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
