# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in OpenDataGov, please report it responsibly.

**Do not open a public GitHub issue.**

Instead, send an email to **security@opendatagov.dev** with:

1. A description of the vulnerability
1. Steps to reproduce
1. Affected component(s) and version(s)
1. Potential impact

You should receive an acknowledgment within **48 hours**. We will work with you to understand the issue and coordinate a fix before any public disclosure.

## Security Measures

### Static Analysis

- **SonarCloud** — continuous code quality and security scanning
- **Trivy** — container image vulnerability scanning on every CI build
- **Ruff / mypy / golangci-lint** — linting and type checking

### Supply Chain

- GitHub Actions are pinned to full commit SHAs
- Docker images use minimal Alpine base images
- Dependencies are locked (`uv.lock`, `go.sum`)

### Runtime

- Containers run as non-root (`odg` user)
- Service account tokens are not auto-mounted in Kubernetes
- Application files are read-only (`--chmod=555`) inside containers
- All inter-service communication uses authenticated endpoints

## Disclosure Timeline

| Step                        | Target   |
| --------------------------- | -------- |
| Acknowledge report          | 48 hours |
| Confirm and assess severity | 5 days   |
| Develop and test fix        | 14 days  |
| Release patch               | 21 days  |
| Public disclosure           | 30 days  |

Timelines may vary depending on severity and complexity.
