# One image: the API plus the built web app (frontend/pwa/dist, if the build step produced it).
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app
RUN useradd --system --uid 10001 app
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY harabhara ./harabhara
COPY config ./config
COPY frontend ./frontend
USER app
# Cloud Run sets PORT; the web app is served from frontend/pwa/dist when it exists
CMD ["sh", "-c", "exec uvicorn harabhara.api.main:build_app --factory --host 0.0.0.0 --port ${PORT:-8080}"]
