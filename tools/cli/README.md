# OpenDataGov CLI

Command-line interface for OpenDataGov governance operations.

## Installation

```bash
pip install odg-cli
```

## Quick Start

### Configure

```bash
# Set API URL
odg config set api_url http://localhost:8000

# Set API key (optional)
odg config set api_key sk_your_key_here

# List configuration
odg config list
```

### Manage Decisions

```bash
# Create a decision
odg decision create \
  --type data_promotion \
  --title "Promote sales to Gold" \
  --description "Quality gates passed" \
  --domain finance \
  --created-by user-1

# List decisions
odg decision list --domain finance --status pending

# Get decision details
odg decision get 123e4567-e89b-12d3-a456-426614174000

# Approve a decision
odg decision approve 123e4567... \
  --voter user-1 \
  --vote approve \
  --comment "Looks good to me"
```

### Manage Datasets

```bash
# List datasets
odg dataset list --layer gold --limit 10

# Search datasets
odg dataset search customer --domain crm
```

### Access Requests

```bash
# Request access
odg access request \
  --dataset gold.customers \
  --requester analyst-1 \
  --purpose "Q1 2024 revenue analysis" \
  --duration 30

# Check request status
odg access get 123e4567-e89b-12d3-a456-426614174000
```

## Configuration

The CLI stores configuration in `~/.odg/config.json`.

Configuration options:

| Key             | Description                     | Default                 |
| --------------- | ------------------------------- | ----------------------- |
| `api_url`       | OpenDataGov API URL             | `http://localhost:8000` |
| `api_key`       | API authentication key          | None                    |
| `timeout`       | Request timeout (seconds)       | `30.0`                  |
| `output_format` | Output format (table/json/yaml) | `table`                 |

### Environment Variables

You can also configure via environment variables with the `ODG_` prefix:

```bash
export ODG_API_URL=http://localhost:8000
export ODG_API_KEY=sk_your_key_here
odg decision list
```

## Commands

### `odg config`

Manage CLI configuration.

```bash
odg config set <key> <value>    # Set configuration value
odg config get <key>             # Get configuration value
odg config list                  # List all configuration
odg config delete <key>          # Delete configuration value
```

### `odg decision`

Manage governance decisions.

```bash
odg decision create [OPTIONS]              # Create decision
odg decision list [OPTIONS]                # List decisions
odg decision get <id>                      # Get decision details
odg decision approve <id> [OPTIONS]        # Cast approval vote
```

**Create Options:**

- `--type` - Decision type (required)
- `--title` - Decision title (required)
- `--description` - Description (required)
- `--domain` - Domain ID (required)
- `--created-by` - Creator user ID (required)

**List Options:**

- `--domain` - Filter by domain
- `--status` - Filter by status (pending, approved, rejected)
- `--limit` - Maximum results (default: 10)

**Approve Options:**

- `--voter` - User casting vote (required)
- `--vote` - Vote type (approve/reject, default: approve)
- `--comment` - Optional comment

### `odg dataset`

Manage datasets.

```bash
odg dataset list [OPTIONS]           # List datasets
odg dataset search <query> [OPTIONS] # Search datasets
```

**List Options:**

- `--layer` - Filter by layer (bronze, silver, gold, platinum)
- `--domain` - Filter by domain
- `--limit` - Maximum results (default: 50)

**Search Options:**

- `--domain` - Filter by domain
- `--layer` - Filter by layer
- `--limit` - Maximum results (default: 20)

### `odg access`

Manage access requests.

```bash
odg access request [OPTIONS]    # Request dataset access
odg access get <id>              # Get request status
```

**Request Options:**

- `--dataset` - Dataset ID (required)
- `--requester` - Requester user ID (required)
- `--purpose` - Purpose of access (required)
- `--duration` - Access duration in days (default: 30)
- `--justification` - Optional justification

## Examples

### Complete Workflow

```bash
# 1. Configure CLI
odg config set api_url http://localhost:8000

# 2. Create a promotion decision
odg decision create \
  --type data_promotion \
  --title "Promote sales dataset to Gold layer" \
  --description "All quality gates passed with score 0.98" \
  --domain finance \
  --created-by engineer-1

# Output: Decision created: 123e4567-e89b-12d3-a456-426614174000

# 3. List pending decisions
odg decision list --domain finance --status pending

# 4. Approve the decision
odg decision approve 123e4567-e89b-12d3-a456-426614174000 \
  --voter data-owner-1 \
  --vote approve \
  --comment "Quality metrics look excellent"

# 5. Search for datasets
odg dataset search sales --layer gold

# 6. Request access to a dataset
odg access request \
  --dataset gold.sales \
  --requester analyst-1 \
  --purpose "Q1 2024 financial analysis" \
  --duration 30

# 7. Check access request status
odg access get <access-request-id>
```

### Scripting

The CLI is designed for use in scripts:

```bash
#!/bin/bash

# Create decisions from a loop
for dataset in sales customers orders; do
  odg decision create \
    --type data_promotion \
    --title "Promote $dataset to Gold" \
    --description "Automated promotion" \
    --domain finance \
    --created-by automation
done

# List all pending decisions in JSON format
export ODG_OUTPUT_FORMAT=json
odg decision list --status pending > pending_decisions.json
```

## Development

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=odg_cli --cov-report=term-missing

# Lint
ruff check src/

# Type checking
mypy src/
```

## Troubleshooting

### Connection Errors

If you get connection errors, check your API URL:

```bash
# Verify configuration
odg config list

# Test connection
curl $(odg config get api_url)/health
```

### Authentication Errors

If you get 401 errors, verify your API key:

```bash
# Check if API key is set
odg config get api_key

# Set API key
odg config set api_key sk_your_actual_key_here
```

### Command Not Found

If `odg` command is not found after installation:

```bash
# Reinstall with --force-reinstall
pip install --force-reinstall odg-cli

# Or use python -m
python -m odg_cli.main --help
```

## License

Apache-2.0
