FROM ghcr.io/astral-sh/uv:0.12.6 AS uv
FROM python:3.13-slim AS runtime

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=uv /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src/lib/pyproject.toml ./src/lib/pyproject.toml
COPY src/lib/butterfly_bot ./src/lib/butterfly_bot
RUN uv sync --frozen --no-dev --no-install-project
COPY src/adonis_blue/__init__.py ./src/adonis_blue/__init__.py
COPY src/adonis_blue/adonis_blue.py ./src/adonis_blue/adonis_blue.py
RUN uv sync --frozen --no-dev

RUN useradd --create-home adonis_blue && chmod -R a-w /app
USER adonis_blue
ENTRYPOINT ["/app/.venv/bin/python", "-m", "adonis_blue.adonis_blue"]
