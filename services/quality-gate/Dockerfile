FROM cgr.dev/chainguard/python:latest-dev AS builder

USER root
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy workspace files needed for dependency resolution
COPY pyproject.toml ./
COPY libs/python/odg-core/ libs/python/odg-core/
COPY services/quality-gate/ services/quality-gate/

# Stub sibling workspace members so uv can resolve the full workspace
COPY services/governance-engine/pyproject.toml services/governance-engine/pyproject.toml
COPY services/lakehouse-agent/pyproject.toml services/lakehouse-agent/pyproject.toml
COPY services/data-expert/pyproject.toml services/data-expert/pyproject.toml
RUN mkdir -p \
        services/governance-engine/src/governance_engine \
        services/lakehouse-agent/src/lakehouse_agent \
        services/data-expert/src/data_expert \
    && touch \
        services/governance-engine/src/governance_engine/__init__.py \
        services/lakehouse-agent/src/lakehouse_agent/__init__.py \
        services/data-expert/src/data_expert/__init__.py

# Install dependencies
WORKDIR /app/services/quality-gate
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

FROM cgr.dev/chainguard/python:latest

COPY --from=ghcr.io/astral-sh/uv:latest --chmod=555 /uv /usr/local/bin/uv

WORKDIR /app
COPY --from=builder --chown=nonroot:nonroot /app /app

USER nonroot
EXPOSE 8000

CMD ["uv", "run", "uvicorn", "quality_gate.main:app", "--host", "0.0.0.0", "--port", "8000"]
