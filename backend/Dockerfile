# Wishly API — the one image we ship to GHCR.
#
#   docker build --build-arg VERSION=$(git rev-parse --short HEAD) -t wishly-api backend/

FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first, our code second. Dependencies change rarely, so Docker
# reuses this layer's cache across most builds and only re-runs the cheap step below.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev

# Never run as root: a compromised process shouldn't own the container.
RUN useradd --uid 10001 wishly
USER wishly

ARG VERSION=dev
# PATH: use the virtualenv's python/uvicorn. PYTHONUNBUFFERED: logs appear
# immediately and aren't lost on a crash. WISHLY_*: read by settings.py.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    WISHLY_ENV=prod \
    WISHLY_VERSION=${VERSION}

EXPOSE 8000

# Exec form (JSON array): uvicorn is PID 1 and receives SIGTERM directly, so
# `docker stop` shuts down gracefully instead of killing it after 10s.
CMD ["uvicorn", "wishly.main:app", "--host", "0.0.0.0", "--port", "8000"]
