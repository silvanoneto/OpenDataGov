FROM python:3.13-alpine AS builder

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml ./
COPY libs/python/odg-core/ libs/python/odg-core/
COPY services/lakehouse-agent/ services/lakehouse-agent/

# Stub sibling workspace members so uv can resolve the full workspace
COPY services/governance-engine/pyproject.toml services/governance-engine/pyproject.toml
COPY services/data-expert/pyproject.toml services/data-expert/pyproject.toml
RUN mkdir -p \
        services/governance-engine/src/governance_engine \
        services/data-expert/src/data_expert \
    && touch \
        services/governance-engine/src/governance_engine/__init__.py \
        services/data-expert/src/data_expert/__init__.py

WORKDIR /app/services/lakehouse-agent
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

FROM python:3.13-alpine

COPY --from=ghcr.io/astral-sh/uv:latest --chmod=555 /uv /usr/local/bin/uv
RUN addgroup -S odg && adduser -S -G odg -h /app odg

WORKDIR /app
COPY --from=builder --chown=odg:odg /app /app

USER odg
EXPOSE 8001

CMD ["uv", "run", "uvicorn", "lakehouse_agent.main:app", "--host", "0.0.0.0", "--port", "8001"]
