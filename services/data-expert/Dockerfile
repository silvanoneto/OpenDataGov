FROM cgr.dev/chainguard/python:latest-dev AS builder

USER root
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml ./
COPY libs/python/odg-core/ libs/python/odg-core/
COPY services/data-expert/ services/data-expert/

# Stub sibling workspace members so uv can resolve the full workspace
COPY services/governance-engine/pyproject.toml services/governance-engine/pyproject.toml
COPY services/lakehouse-agent/pyproject.toml services/lakehouse-agent/pyproject.toml
COPY services/quality-gate/pyproject.toml services/quality-gate/pyproject.toml
RUN mkdir -p \
        services/governance-engine/src/governance_engine \
        services/lakehouse-agent/src/lakehouse_agent \
        services/quality-gate/src/quality_gate \
    && touch \
        services/governance-engine/src/governance_engine/__init__.py \
        services/lakehouse-agent/src/lakehouse_agent/__init__.py \
        services/quality-gate/src/quality_gate/__init__.py

WORKDIR /app/services/data-expert
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

FROM cgr.dev/chainguard/python:latest

COPY --from=ghcr.io/astral-sh/uv:latest --chmod=555 /uv /usr/local/bin/uv

WORKDIR /app
COPY --from=builder --chown=nonroot:nonroot /app /app

USER nonroot
EXPOSE 8002

CMD ["uv", "run", "uvicorn", "data_expert.main:app", "--host", "0.0.0.0", "--port", "8002"]
