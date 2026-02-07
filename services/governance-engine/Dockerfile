FROM python:3.13-alpine AS builder

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy workspace files needed for dependency resolution
COPY pyproject.toml ./
COPY libs/python/odg-core/ libs/python/odg-core/
COPY services/governance-engine/ services/governance-engine/

# Stub sibling workspace members so uv can resolve the full workspace
COPY services/lakehouse-agent/pyproject.toml services/lakehouse-agent/pyproject.toml
COPY services/data-expert/pyproject.toml services/data-expert/pyproject.toml
RUN mkdir -p \
        services/lakehouse-agent/src/lakehouse_agent \
        services/data-expert/src/data_expert \
    && touch \
        services/lakehouse-agent/src/lakehouse_agent/__init__.py \
        services/data-expert/src/data_expert/__init__.py

# Install dependencies
WORKDIR /app/services/governance-engine
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

FROM python:3.13-alpine

COPY --from=ghcr.io/astral-sh/uv:latest --chmod=555 /uv /usr/local/bin/uv
RUN addgroup -S odg && adduser -S -G odg -h /app odg

WORKDIR /app
COPY --from=builder --chown=odg:odg /app /app

USER odg
EXPOSE 8000

CMD ["uv", "run", "uvicorn", "governance_engine.main:app", "--host", "0.0.0.0", "--port", "8000"]
