FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md alembic.ini ./
COPY src ./src
COPY alembic ./alembic

RUN uv sync --frozen --no-dev

EXPOSE 8000

# Applies migrations on boot, then serves the app (architecture decision, section 29).
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn safetour.main:app --host 0.0.0.0 --port 8000"]
