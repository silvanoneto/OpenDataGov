# CLI Tool Guide

## Overview

The OpenDataGov CLI (`odg`) provides a command-line interface for managing governance decisions, datasets, and access requests. It's built on top of the Python SDK and designed for both interactive use and automation.

## Installation

```bash
pip install odg-cli
```

Verify installation:

```bash
odg --version
# Output: odg, version 0.1.0
```

## Quick Start

### 1. Configure

```bash
# Set API URL
odg config set api_url http://localhost:8000

# Optional: Set API key for authentication
odg config set api_key sk_your_api_key_here

# Verify configuration
odg config list
```

### 2. Create a Decision

```bash
odg decision create \
  --type data_promotion \
  --title "Promote sales dataset to Gold" \
  --description "All quality gates passed" \
  --domain finance \
  --created-by engineer-1
```

### 3. List Decisions

```bash
odg decision list --domain finance --status pending
```

### 4. Approve a Decision

```bash
odg decision approve <decision-id> \
  --voter data-owner-1 \
  --vote approve \
  --comment "Quality metrics look excellent"
```

## Configuration

### Config File

Configuration is stored in `~/.odg/config.json`:

```json
{
  "api_url": "http://localhost:8000",
  "api_key": "sk_your_key_here",
  "timeout": 30.0,
  "output_format": "table"
}
```

### Configuration Commands

```bash
# Set a value
odg config set <key> <value>

# Get a value
odg config get <key>

# List all configuration
odg config list

# Delete a value (reset to default)
odg config delete <key>
```

### Configuration Options

| Key             | Type   | Default                 | Description                     |
| --------------- | ------ | ----------------------- | ------------------------------- |
| `api_url`       | string | `http://localhost:8000` | OpenDataGov API URL             |
| `api_key`       | string | None                    | API authentication key          |
| `timeout`       | float  | `30.0`                  | Request timeout in seconds      |
| `output_format` | string | `table`                 | Output format (table/json/yaml) |

### Environment Variables

Override configuration with environment variables (prefix: `ODG_`):

```bash
export ODG_API_URL=http://localhost:8000
export ODG_API_KEY=sk_your_key_here
export ODG_TIMEOUT=60

# Now odg commands use these values
odg decision list
```

## Commands

### Global Options

All commands support these global options:

```bash
odg --help           # Show help
odg --version        # Show version
```

## Decision Commands

Manage governance decisions and approvals.

### `odg decision create`

Create a new governance decision.

**Usage:**

```bash
odg decision create [OPTIONS]
```

**Options:**

| Option          | Required | Description                                         |
| --------------- | -------- | --------------------------------------------------- |
| `--type`        | Yes      | Decision type (e.g., data_promotion, schema_change) |
| `--title`       | Yes      | Decision title                                      |
| `--description` | Yes      | Detailed description                                |
| `--domain`      | Yes      | Domain ID                                           |
| `--created-by`  | Yes      | User creating the decision                          |

**Example:**

```bash
odg decision create \
  --type data_promotion \
  --title "Promote sales dataset to Gold layer" \
  --description "All quality gates passed with score 0.98" \
  --domain finance \
  --created-by engineer-1

# Output:
# ✓ Decision created: 123e4567-e89b-12d3-a456-426614174000
#   Status: pending
```

### `odg decision list`

List governance decisions with optional filters.

**Usage:**

```bash
odg decision list [OPTIONS]
```

**Options:**

| Option     | Required | Default | Description                                  |
| ---------- | -------- | ------- | -------------------------------------------- |
| `--domain` | No       | All     | Filter by domain                             |
| `--status` | No       | All     | Filter by status (pending/approved/rejected) |
| `--limit`  | No       | 10      | Maximum number of results                    |

**Examples:**

```bash
# List all decisions
odg decision list

# Filter by domain and status
odg decision list --domain finance --status pending

# Show more results
odg decision list --limit 50
```

**Output:**

```
┌──────────┬──────────────────┬───────────────┬─────────┬────────┐
│ ID       │ Title            │ Type          │ Status  │ Domain │
├──────────┼──────────────────┼───────────────┼─────────┼────────┤
│ 123e4567 │ Promote sales... │ data_promotion│ pending │finance │
│ 234f5678 │ Schema change... │ schema_change │ pending │crm     │
└──────────┴──────────────────┴───────────────┴─────────┴────────┘

Showing 2 of 2 decisions
```

### `odg decision get`

Get detailed information about a specific decision.

**Usage:**

```bash
odg decision get <decision-id>
```

**Example:**

```bash
odg decision get 123e4567-e89b-12d3-a456-426614174000
```

**Output:**

```
Decision 123e4567-e89b-12d3-a456-426614174000

Title:       Promote sales dataset to Gold layer
Type:        data_promotion
Status:      pending
Domain:      finance
Created by:  engineer-1
Created at:  2024-02-08T10:30:00Z

Metadata:
  source_layer: silver
  target_layer: gold
  quality_score: 0.98
```

### `odg decision approve`

Cast an approval vote on a decision.

**Usage:**

```bash
odg decision approve <decision-id> [OPTIONS]
```

**Options:**

| Option      | Required | Default | Description                |
| ----------- | -------- | ------- | -------------------------- |
| `--voter`   | Yes      | -       | User ID casting the vote   |
| `--vote`    | No       | approve | Vote type (approve/reject) |
| `--comment` | No       | -       | Optional comment           |

**Examples:**

```bash
# Approve
odg decision approve 123e4567-e89b-12d3-a456-426614174000 \
  --voter data-owner-1 \
  --vote approve \
  --comment "Quality metrics look excellent"

# Reject
odg decision approve 123e4567-e89b-12d3-a456-426614174000 \
  --voter compliance-officer \
  --vote reject \
  --comment "Missing compliance documentation"
```

**Output:**

```
✓ Vote cast: approve
  Decision status: approved
```

## Dataset Commands

Manage and search datasets.

### `odg dataset list`

List datasets with optional filters.

**Usage:**

```bash
odg dataset list [OPTIONS]
```

**Options:**

| Option     | Required | Default | Description                                   |
| ---------- | -------- | ------- | --------------------------------------------- |
| `--layer`  | No       | All     | Filter by layer (bronze/silver/gold/platinum) |
| `--domain` | No       | All     | Filter by domain                              |
| `--limit`  | No       | 50      | Maximum number of results                     |

**Examples:**

```bash
# List all datasets
odg dataset list

# Filter by layer
odg dataset list --layer gold

# Filter by domain and layer
odg dataset list --domain finance --layer gold --limit 10
```

**Output:**

```
┌───────────────┬───────────┬───────┬────────────────┬──────────────┐
│ ID            │ Name      │ Layer │ Classification │ Quality Score│
├───────────────┼───────────┼───────┼────────────────┼──────────────┤
│ gold.customers│ customers │ gold  │ sensitive      │ 0.95         │
│ gold.sales    │ sales     │ gold  │ internal       │ 0.98         │
└───────────────┴───────────┴───────┴────────────────┴──────────────┘

Showing 2 datasets
```

### `odg dataset search`

Search datasets by name or description.

**Usage:**

```bash
odg dataset search <query> [OPTIONS]
```

**Options:**

| Option     | Required | Default | Description               |
| ---------- | -------- | ------- | ------------------------- |
| `--domain` | No       | All     | Filter by domain          |
| `--layer`  | No       | All     | Filter by layer           |
| `--limit`  | No       | 20      | Maximum number of results |

**Examples:**

```bash
# Search by keyword
odg dataset search customer

# Search with filters
odg dataset search sales --domain finance --layer gold
```

**Output:**

```
Search Results: 'customer'

┌────────────────┬───────────┬─────────────────────┬───────┐
│ ID             │ Name      │ Description         │ Layer │
├────────────────┼───────────┼─────────────────────┼───────┤
│ gold.customers │ customers │ Customer master ... │ gold  │
│ silver.cust... │ customers │ Customer raw data   │silver │
└────────────────┴───────────┴─────────────────────┴───────┘

Found 2 datasets
```

## Access Request Commands

Request and manage dataset access.

### `odg access request`

Request access to a dataset.

**Usage:**

```bash
odg access request [OPTIONS]
```

**Options:**

| Option            | Required | Default | Description                      |
| ----------------- | -------- | ------- | -------------------------------- |
| `--dataset`       | Yes      | -       | Dataset ID to access             |
| `--requester`     | Yes      | -       | User requesting access           |
| `--purpose`       | Yes      | -       | Purpose of access (min 10 chars) |
| `--duration`      | No       | 30      | Access duration in days (1-365)  |
| `--justification` | No       | -       | Optional justification           |

**Example:**

```bash
odg access request \
  --dataset gold.customers \
  --requester analyst-1 \
  --purpose "Q1 2024 revenue analysis for board presentation" \
  --duration 30 \
  --justification "Need customer data to generate quarterly report"
```

**Output:**

```
✓ Access request created: 456f7890-ab12-cd34-ef56-789012345678
  Dataset:  gold.customers
  Status:   pending
  Purpose:  Q1 2024 revenue analysis for board presentation
  Decision: 123e4567-e89b-12d3-a456-426614174000
```

### `odg access get`

Get access request status.

**Usage:**

```bash
odg access get <request-id>
```

**Example:**

```bash
odg access get 456f7890-ab12-cd34-ef56-789012345678
```

**Output:**

```
Access Request 456f7890-ab12-cd34-ef56-789012345678

Dataset:    gold.customers
Requester:  analyst-1
Status:     pending
Purpose:    Q1 2024 revenue analysis for board presentation
Created:    2024-02-08T14:30:00Z
Decision:   123e4567-e89b-12d3-a456-426614174000
```

## Output Formats

### Table Format (Default)

Pretty-printed tables for human readability:

```bash
odg decision list
```

### JSON Format

Machine-readable JSON output:

```bash
export ODG_OUTPUT_FORMAT=json
odg decision list

# Or inline
ODG_OUTPUT_FORMAT=json odg decision list > decisions.json
```

### YAML Format

YAML output for configuration:

```bash
export ODG_OUTPUT_FORMAT=yaml
odg config list
```

## Complete Workflows

### Promote Dataset to Gold

```bash
#!/bin/bash
set -e

DATASET_ID="silver.sales"
USER_ID="engineer-1"

echo "1. Creating promotion decision..."
DECISION_ID=$(odg decision create \
  --type data_promotion \
  --title "Promote $DATASET_ID to Gold" \
  --description "Quality validation passed" \
  --domain finance \
  --created-by $USER_ID \
  | grep "Decision created:" | cut -d: -f2 | tr -d ' ')

echo "Decision ID: $DECISION_ID"

echo "2. Waiting for approvals..."
odg decision get $DECISION_ID

echo "3. Done! Check status with:"
echo "  odg decision get $DECISION_ID"
```

### Bulk Access Requests

```bash
#!/bin/bash

# Request access to multiple datasets
DATASETS=(
  "gold.customers"
  "gold.sales"
  "gold.transactions"
)

for dataset in "${DATASETS[@]}"; do
  echo "Requesting access to $dataset..."

  odg access request \
    --dataset $dataset \
    --requester analyst-1 \
    --purpose "Q1 2024 financial analysis" \
    --duration 30

  sleep 1
done

echo "All access requests submitted"
```

### Monitor Pending Decisions

```bash
#!/bin/bash

# Poll for pending decisions every 30 seconds
while true; do
  clear
  echo "=== Pending Decisions ==="
  echo ""

  odg decision list --status pending --limit 20

  echo ""
  echo "Last updated: $(date)"
  echo "Press Ctrl+C to stop"

  sleep 30
done
```

## Scripting & Automation

### CI/CD Integration

```yaml
# .github/workflows/governance.yml
name: Governance Checks

on: [pull_request]

jobs:
  check-quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Install ODG CLI
        run: pip install odg-cli

      - name: Configure CLI
        run: |
          odg config set api_url ${{ secrets.ODG_API_URL }}
          odg config set api_key ${{ secrets.ODG_API_KEY }}

      - name: Create promotion decision
        run: |
          odg decision create \
            --type data_promotion \
            --title "Promote ${{ github.event.pull_request.title }}" \
            --description "PR #${{ github.event.pull_request.number }}" \
            --domain ${{ inputs.domain }} \
            --created-by github-actions

      - name: List pending decisions
        run: odg decision list --status pending
```

### Cron Jobs

```bash
# crontab entry: Daily access request summary
0 9 * * * /usr/local/bin/odg decision list --status pending | mail -s "Pending Approvals" team@example.com
```

### Shell Functions

```bash
# Add to ~/.bashrc or ~/.zshrc

# Quick decision approval
approve_decision() {
  local decision_id=$1
  local voter=${2:-$USER}
  local comment=${3:-"Approved via CLI"}

  odg decision approve $decision_id \
    --voter $voter \
    --vote approve \
    --comment "$comment"
}

# Usage: approve_decision 123e4567... data-owner-1 "LGTM"
```

## Troubleshooting

### Command Not Found

```bash
# Verify installation
pip show odg-cli

# If not found, install
pip install odg-cli

# Check PATH
which odg

# If still not found, use module invocation
python -m odg_cli.main --help
```

### Connection Errors

```bash
# Check configuration
odg config list

# Verify API is accessible
curl $(odg config get api_url)/health

# Test with explicit URL
ODG_API_URL=http://localhost:8000 odg decision list
```

### Authentication Errors

```bash
# Check API key
odg config get api_key

# Set API key
odg config set api_key sk_your_actual_key

# Test without API key (if API allows)
odg config delete api_key
odg decision list
```

### Timeout Errors

```bash
# Increase timeout
odg config set timeout 60

# Or via environment
ODG_TIMEOUT=120 odg decision list --limit 1000
```

### Output Format Issues

```bash
# Reset output format
odg config delete output_format

# Force table format
ODG_OUTPUT_FORMAT=table odg decision list
```

## Tips & Best Practices

### 1. Use Aliases

```bash
# Add to ~/.bashrc
alias odg-pending='odg decision list --status pending'
alias odg-approve='odg decision approve'
alias odg-search='odg dataset search'
```

### 2. Save Output

```bash
# Export to JSON
odg decision list --limit 100 > decisions.json

# Use jq for processing
odg decision list | jq '.[] | select(.status == "pending")'
```

### 3. Check Before Acting

```bash
# Always review before approving
odg decision get $DECISION_ID
read -p "Approve? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  odg decision approve $DECISION_ID --voter $USER --vote approve
fi
```

### 4. Use Configuration Profiles

```bash
# Dev environment
export ODG_API_URL=http://localhost:8000

# Staging
export ODG_API_URL=https://staging.opendatagov.com
export ODG_API_KEY=$STAGING_KEY

# Production
export ODG_API_URL=https://api.opendatagov.com
export ODG_API_KEY=$PROD_KEY
```

## Advanced Usage

### Custom Output Processing

```bash
# Extract decision IDs
odg decision list | grep "Decision created" | cut -d: -f2

# Count pending decisions
odg decision list --status pending | grep -c "pending"

# Format as CSV
odg decision list --format json | jq -r '.[] | [.id, .title, .status] | @csv'
```

### Batch Operations

```bash
# Approve all pending decisions (use with caution!)
for id in $(odg decision list --status pending --format json | jq -r '.[].id'); do
  echo "Approving $id..."
  odg decision approve $id --voter auto-approver --vote approve
done
```

### Integration with Other Tools

```bash
# Send to Slack
odg decision list --status pending | \
  slack-cli send --channel governance --message "Pending approvals: @here"

# Update Jira
odg decision get $DECISION_ID | \
  jira-cli issue comment $JIRA_TICKET --stdin
```

## Uninstallation

```bash
# Uninstall CLI
pip uninstall odg-cli

# Remove configuration
rm -rf ~/.odg
```

## Source Code

GitHub: https://github.com/opendatagov/opendatagov/tree/main/tools/cli

## See Also

- [Python SDK Guide](SDK.md)
- [GraphQL API Reference](API_GRAPHQL.md)
- [gRPC API Reference](API_GRPC.md)
