FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
RUN uv sync --locked --no-dev
ENV PATH="/app/.venv/bin:$PATH" LOGOS_DATABASE_PATH=/app/data/logos.sqlite3
EXPOSE 8000
CMD ["uvicorn", "logos_backend.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
