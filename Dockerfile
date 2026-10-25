# CLI-only image. Native interception still depends on host kernel/permissions.
FROM ghcr.io/astral-sh/uv:0.12.22 AS uv
FROM python:3.14-slim-bookworm AS builder
COPY --from=uv /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
COPY pyproject.toml uv.lock .python-version README.md LICENSE hatch_build.py babel.cfg ./
COPY src/ ./src/
RUN uv sync --locked --no-dev --no-editable

FROM python:3.14-slim-bookworm
LABEL org.opencontainers.image.source="https://github.com/anosora233/majsoul-hook-mitm" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libstdc++6 libgomp1 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" MAJSOUL_HOOK_HOME=/workspace PYTHONUNBUFFERED=1
RUN useradd --uid 10001 --create-home app && mkdir /workspace && chown app:app /workspace
WORKDIR /workspace
USER app
ENTRYPOINT ["majsoul-hook"]
CMD ["--help"]
