# Official Playwright Python image. The tag must match the playwright version in uv.lock.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /uvx /bin/

WORKDIR /work
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .
RUN uv sync --frozen --no-dev

ENV CI=true \
    HEADLESS=true \
    IN_DOCKER=true

CMD ["uv", "run", "pytest", "-m", "not visual"]
