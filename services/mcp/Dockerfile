FROM python:3.11-slim-trixie@sha256:e41613d42d4891e4930f79523f93f81bbc7632584ec65e36ab055f41a800b41e AS build

ENV UV_NO_PROGRESS=1
WORKDIR /app
RUN python -m pip install --no-cache-dir uv==0.9.23
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable --python /usr/local/bin/python && uv cache clean

FROM python:3.11-slim-trixie@sha256:e41613d42d4891e4930f79523f93f81bbc7632584ec65e36ab055f41a800b41e

ARG SOURCE_COMMIT
ARG LOCK_SHA256
LABEL org.opencontainers.image.source="https://github.com/BuriAhmad/sakai-mcp" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.title="Sakai MCP" \
      org.opencontainers.image.description="Delegated Sakai MCP service" \
      org.opencontainers.image.licenses="ECL-2.0" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.uv-lock-sha256="${LOCK_SHA256}"
RUN /usr/local/bin/python -m pip uninstall -y pip setuptools wheel && \
    groupadd --system --gid 10001 mcp && \
    useradd --system --uid 10001 --gid mcp --home-dir /nonexistent --shell /usr/sbin/nologin mcp
WORKDIR /app
COPY --from=build --chown=10001:10001 /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "sakai_mcp.asgi:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
