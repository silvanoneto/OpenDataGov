# Contributing to OpenDataGov

Thank you for your interest in contributing to OpenDataGov!

## Development Setup

1. **Prerequisites**: Python 3.13+, [uv](https://docs.astral.sh/uv/), Go 1.25+, Docker
1. **Clone**: `git clone https://github.com/silvanoneto/OpenDataGov.git`
1. **Setup**: `make install` (installs deps + pre-commit hooks)
1. **Run linters**: `make lint`
1. **Run tests**: `make test`

## Code Standards

### Python

- Formatter/linter: **ruff** (configured in `pyproject.toml`)
- Type checking: **mypy** in strict mode
- Testing: **pytest** with coverage target of 95%
- Models: **Pydantic V2** for all data models
- Async-first: use `async/await` for I/O operations

### Go

- Linter: **golangci-lint**
- Follow standard Go project layout

### General

- Code in **English** (variables, functions, comments)
- Documentation in **English** (PT-BR and ZH translations welcome)
- Commit messages in English, following [Conventional Commits](https://www.conventionalcommits.org/)

## Pull Request Process

1. Fork the repository
1. Create a feature branch from `main`
1. Write tests for new functionality
1. Ensure `make lint` and `make test` pass
1. Submit a PR with a clear description

## Architecture Decisions

All architectural decisions are documented as ADRs in [docs/ARCHITECTURE_DECISIONS.md](docs/ARCHITECTURE_DECISIONS.md). New proposals should follow the same format.

## License

By contributing, you agree that your contributions will be licensed under Apache-2.0.
