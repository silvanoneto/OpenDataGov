# ADR-097: FinOps Dashboard - Cloud Cost Monitoring & Optimization

**Status:** Accepted
**Date:** 2026-02-08
**Authors:** Engineering Team
**Priority:** P2 (Optimization Phase)

______________________________________________________________________

## Context

OpenDataGov runs across multiple cloud providers (AWS, GCP, Azure) with growing infrastructure costs:

- **Current Monthly Spend:** ~$15,000/month
- **Growth Rate:** 15% MoM (as customer base expands)
- **Pain Points:**
  - No unified view of costs across clouds
  - Difficult to allocate costs to specific projects/teams
  - No proactive alerts for budget overruns
  - Manual cost optimization (reactive, not proactive)
  - No forecasting or trend analysis

**Business Impact:**

- Wasted spend on idle resources (estimated 20-30%)
- Unpredictable cloud bills
- Cannot charge back costs to internal teams
- No visibility into ROI per service

**Goal:** Build a comprehensive FinOps dashboard to track, analyze, and optimize cloud costs in real-time.

______________________________________________________________________

## Decision

Implement a **FinOps Dashboard** with the following components:

### 1. Multi-Cloud Cost Collection

- Integrate with AWS Cost Explorer API, GCP Billing API, Azure Cost Management API
- Ingest cost data every 6 hours (API rate limits)
- Store in TimescaleDB for time-series cost analysis
- Tag-based cost allocation (project, team, environment, service)

### 2. Budget Tracking & Alerting

- Set budgets at multiple levels: organization, project, service, environment
- Real-time budget burn rate calculation
- Alerts at 50%, 80%, 100%, 120% thresholds
- Forecast when budget will be exhausted (ML-based)

### 3. Anomaly Detection

- Detect cost spikes using statistical methods (Z-score, IQR)
- ML model to learn normal spending patterns
- Slack/email alerts for anomalies (e.g., "EC2 costs up 300% today")

### 4. Savings Recommendations

- **Rightsizing:** Identify underutilized instances (CPU < 20%, Memory < 30%)
- **Reserved Instances:** Recommend RI purchases based on usage patterns
- **Spot Instances:** Suggest workloads suitable for spot (batch jobs, dev/test)
- **Idle Resources:** Detect stopped instances, unattached volumes, old snapshots
- **Storage Optimization:** Move S3 data to Glacier, delete old logs

### 5. Cost Allocation

- Allocate costs by:
  - **Project:** lakehouse-agent, governance-engine, support-portal
  - **Team:** Platform, Data, Engineering
  - **Environment:** production, staging, development
  - **Service:** Kubernetes, RDS, S3, Elasticsearch
- Chargeback reports for internal billing

### 6. Grafana Dashboard

- Real-time cost tracking (today, MTD, YTD)
- Budget vs. actual burn rate
- Cost breakdown (service, project, team)
- Savings opportunities (top 10)
- Forecasted spend (next 30/90 days)

______________________________________________________________________

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────┐
│  Cloud Providers                                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │   AWS    │  │   GCP    │  │  Azure   │             │
│  │  Cost    │  │  Billing │  │   Cost   │             │
│  │ Explorer │  │   API    │  │   Mgmt   │             │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘             │
└───────┼─────────────┼─────────────┼───────────────────┘
        │             │             │
        ▼             ▼             ▼
┌────────────────────────────────────────────────────┐
│  Cost Collector Service (Python)                  │
│  - Fetch costs from AWS/GCP/Azure every 6h        │
│  - Parse and normalize cost data                  │
│  - Tag extraction and validation                  │
│  - Store in TimescaleDB                           │
└────────────────────┬───────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  TimescaleDB (PostgreSQL) │
        │  Tables:                │
        │  - cloud_costs          │
        │  - budgets              │
        │  - anomalies            │
        │  - recommendations      │
        └────────┬────────────────┘
                 │
      ┏━━━━━━━━━┻━━━━━━━━━┓
      ▼                    ▼
┌──────────────┐   ┌──────────────────┐
│  Budget      │   │  Anomaly         │
│  Monitor     │   │  Detector        │
│  (Cron)      │   │  (Cron)          │
│              │   │                  │
│  - Check     │   │  - Statistical   │
│    budgets   │   │    analysis      │
│  - Calculate │   │  - ML model      │
│    burn rate │   │  - Threshold     │
│  - Forecast  │   │    detection     │
│  - Alert     │   │  - Alert         │
└──────────────┘   └──────────────────┘
      │                    │
      └────────┬───────────┘
               │
               ▼
      ┌────────────────┐
      │  Alertmanager  │
      │  - Slack       │
      │  - Email       │
      │  - PagerDuty   │
      └────────────────┘
               │
               ▼
      ┌────────────────────────┐
      │  Grafana Dashboard     │
      │  - Cost overview       │
      │  - Budget burn rate    │
      │  - Top spenders        │
      │  - Savings opps        │
      │  - Forecasts           │
      └────────────────────────┘
```

### Data Model

#### cloud_costs (TimescaleDB Hypertable)

```sql
CREATE TABLE cloud_costs (
    time TIMESTAMPTZ NOT NULL,
    cloud_provider VARCHAR(10) NOT NULL,  -- aws, gcp, azure
    account_id VARCHAR(50) NOT NULL,
    service VARCHAR(100) NOT NULL,  -- ec2, rds, s3, gke, cloud-storage, etc.
    region VARCHAR(50),

    -- Cost data
    cost DECIMAL(12, 4) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',

    -- Resource details
    resource_id VARCHAR(200),
    resource_name VARCHAR(200),

    -- Tags (for cost allocation)
    tags JSONB,  -- {project: "lakehouse-agent", team: "platform", env: "production"}

    -- Derived fields
    project VARCHAR(100),
    team VARCHAR(100),
    environment VARCHAR(50),

    PRIMARY KEY (time, cloud_provider, account_id, service)
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('cloud_costs', 'time');

-- Indexes for common queries
CREATE INDEX idx_cloud_costs_project ON cloud_costs (project, time DESC);
CREATE INDEX idx_cloud_costs_service ON cloud_costs (service, time DESC);
CREATE INDEX idx_cloud_costs_tags ON cloud_costs USING GIN (tags);
```

#### budgets

```sql
CREATE TABLE budgets (
    budget_id SERIAL PRIMARY KEY,
    budget_name VARCHAR(200) NOT NULL,

    -- Scope
    scope_type VARCHAR(50) NOT NULL,  -- organization, project, team, service, environment
    scope_value VARCHAR(200),  -- e.g., "lakehouse-agent", "platform", "production"

    -- Budget config
    amount DECIMAL(12, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    period VARCHAR(20) NOT NULL,  -- monthly, quarterly, yearly

    -- Alerts
    alert_thresholds JSONB,  -- [50, 80, 100, 120]
    alert_channels JSONB,  -- {slack: "#finops", email: ["team@..."], pagerduty: false}

    -- Metadata
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    active BOOLEAN DEFAULT TRUE
);
```

#### cost_anomalies

```sql
CREATE TABLE cost_anomalies (
    anomaly_id SERIAL PRIMARY KEY,
    detected_at TIMESTAMPTZ NOT NULL,

    -- Anomaly details
    cloud_provider VARCHAR(10),
    service VARCHAR(100),
    project VARCHAR(100),

    -- Cost info
    expected_cost DECIMAL(12, 4),
    actual_cost DECIMAL(12, 4),
    deviation_pct DECIMAL(5, 2),  -- 300% = 3x expected

    -- Detection method
    detection_method VARCHAR(50),  -- zscore, iqr, ml_model
    confidence_score DECIMAL(3, 2),  -- 0.95 = 95% confidence

    -- Status
    status VARCHAR(20) DEFAULT 'open',  -- open, investigating, resolved, false_positive
    resolution_notes TEXT,
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(100)
);
```

#### savings_recommendations

```sql
CREATE TABLE savings_recommendations (
    recommendation_id SERIAL PRIMARY KEY,
    generated_at TIMESTAMPTZ NOT NULL,

    -- Recommendation type
    type VARCHAR(50) NOT NULL,  -- rightsizing, reserved_instance, spot_instance, idle_resource, storage_optimization
    priority VARCHAR(20),  -- critical, high, medium, low

    -- Resource details
    cloud_provider VARCHAR(10),
    service VARCHAR(100),
    resource_id VARCHAR(200),
    resource_name VARCHAR(200),

    -- Savings potential
    current_monthly_cost DECIMAL(12, 2),
    projected_monthly_cost DECIMAL(12, 2),
    monthly_savings DECIMAL(12, 2),
    annual_savings DECIMAL(12, 2),

    -- Recommendation details
    description TEXT,
    action_required TEXT,  -- e.g., "Downsize from m5.2xlarge to m5.xlarge"

    -- Implementation
    status VARCHAR(20) DEFAULT 'pending',  -- pending, approved, implemented, rejected
    implemented_at TIMESTAMPTZ,
    implemented_by VARCHAR(100)
);
```

______________________________________________________________________

## API Design

### Cost Collector Service

**Endpoint:** `/api/v1/finops/costs/collect`

```python
@router.post("/collect")
async def collect_costs(
    cloud_provider: Literal["aws", "gcp", "azure"],
    start_date: date,
    end_date: date,
    db: AsyncSession = Depends(get_db)
) -> CollectionResult:
    """Manually trigger cost collection."""
    collector = get_collector(cloud_provider)
    costs = await collector.fetch_costs(start_date, end_date)

    # Store in TimescaleDB
    await db.execute(insert(CloudCostRow).values(costs))
    await db.commit()

    return CollectionResult(
        records_inserted=len(costs),
        total_cost=sum(c.cost for c in costs),
        date_range=(start_date, end_date)
    )
```

### Budget Tracking

**Endpoint:** `/api/v1/finops/budgets`

```python
@router.post("/budgets")
async def create_budget(budget: BudgetCreate) -> Budget:
    """Create new budget."""
    pass

@router.get("/budgets/{budget_id}/status")
async def get_budget_status(budget_id: int) -> BudgetStatus:
    """Get current budget status."""
    # Calculate spend so far this period
    # Calculate burn rate
    # Forecast when budget will be exhausted
    return BudgetStatus(
        budget_id=budget_id,
        amount=10000.00,
        spent_to_date=7500.00,
        remaining=2500.00,
        pct_consumed=75.0,
        burn_rate_per_day=300.00,
        forecast_exhaustion_date="2026-02-16",
        on_track=False
    )
```

### Anomaly Detection

**Endpoint:** `/api/v1/finops/anomalies`

```python
@router.get("/anomalies")
async def list_anomalies(
    status: str = "open",
    days: int = 7
) -> list[Anomaly]:
    """List recent cost anomalies."""
    pass

@router.post("/anomalies/{anomaly_id}/resolve")
async def resolve_anomaly(
    anomaly_id: int,
    resolution: AnomalyResolution
) -> Anomaly:
    """Mark anomaly as resolved or false positive."""
    pass
```

### Savings Recommendations

**Endpoint:** `/api/v1/finops/recommendations`

```python
@router.get("/recommendations")
async def list_recommendations(
    type: str | None = None,
    min_savings: float = 0
) -> list[Recommendation]:
    """List cost savings recommendations."""
    pass

@router.post("/recommendations/{rec_id}/approve")
async def approve_recommendation(rec_id: int) -> Recommendation:
    """Approve recommendation for implementation."""
    pass
```

______________________________________________________________________

## Implementation Plan

### Phase 1: Core Cost Collection (Week 1-2)

- [ ] Implement AWS Cost Explorer integration
- [ ] Implement GCP Billing API integration
- [ ] Implement Azure Cost Management API integration
- [ ] TimescaleDB schema setup
- [ ] Cron job for automated collection (every 6h)

### Phase 2: Budget Tracking (Week 3)

- [ ] Budget CRUD API
- [ ] Budget monitoring cron job
- [ ] Burn rate calculation
- [ ] Forecast algorithm (linear regression)
- [ ] Alerting integration (Slack, email)

### Phase 3: Anomaly Detection (Week 4)

- [ ] Statistical anomaly detection (Z-score, IQR)
- [ ] ML model training (Prophet for forecasting)
- [ ] Anomaly alert system
- [ ] False positive management

### Phase 4: Savings Recommendations (Week 5-6)

- [ ] Rightsizing analyzer (CloudWatch metrics)
- [ ] Reserved Instance recommender
- [ ] Idle resource detector
- [ ] Storage optimization analyzer
- [ ] Recommendation approval workflow

### Phase 5: Grafana Dashboard (Week 7)

- [ ] Cost overview panel
- [ ] Budget burn rate gauges
- [ ] Top spenders table
- [ ] Savings opportunities list
- [ ] Cost forecast chart

______________________________________________________________________

## Cloud Provider APIs

### AWS Cost Explorer

```python
import boto3
from datetime import datetime, timedelta

ce = boto3.client('ce', region_name='us-east-1')

response = ce.get_cost_and_usage(
    TimePeriod={
        'Start': '2026-02-01',
        'End': '2026-02-08'
    },
    Granularity='DAILY',
    Metrics=['UnblendedCost'],
    GroupBy=[
        {'Type': 'DIMENSION', 'Key': 'SERVICE'},
        {'Type': 'TAG', 'Key': 'project'}
    ]
)
```

### GCP Billing API

```python
from google.cloud import billing_v1

client = billing_v1.CloudBillingClient()

# Query BigQuery export table
from google.cloud import bigquery
bq_client = bigquery.Client()

query = """
SELECT
  service.description AS service,
  SUM(cost) AS total_cost,
  labels.value AS project
FROM `project.dataset.gcp_billing_export_v1_*`
WHERE DATE(_PARTITIONTIME) BETWEEN '2026-02-01' AND '2026-02-08'
GROUP BY service, project
"""

results = bq_client.query(query)
```

### Azure Cost Management API

```python
from azure.mgmt.costmanagement import CostManagementClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
client = CostManagementClient(credential)

query = {
    "type": "Usage",
    "timeframe": "Custom",
    "timePeriod": {
        "from": "2026-02-01",
        "to": "2026-02-08"
    },
    "dataset": {
        "granularity": "Daily",
        "aggregation": {
            "totalCost": {"name": "Cost", "function": "Sum"}
        },
        "grouping": [
            {"type": "Dimension", "name": "ServiceName"},
            {"type": "Tag", "name": "project"}
        ]
    }
}

result = client.query.usage(scope="/subscriptions/{subscription-id}", parameters=query)
```

______________________________________________________________________

## Metrics & Alerts

### Key Metrics

| Metric              | Description                           | Alert Threshold      |
| ------------------- | ------------------------------------- | -------------------- |
| Daily spend         | Total cost today                      | > 2x avg daily spend |
| Monthly burn rate   | Projected monthly spend               | > budget             |
| Top service cost    | Highest cost service                  | > 40% of total       |
| Idle resource count | Stopped instances, unattached volumes | > 20 resources       |
| Savings potential   | Total monthly savings available       | > $5,000             |

### Alert Examples

**Budget Overrun:**

```
🚨 Budget Alert: Production Budget

Budget: $10,000/month
Spent: $8,200 (82%)
Burn rate: $400/day
Forecast: Will exceed budget on Feb 25 (7 days early)

Action: Review top spenders in Grafana dashboard
```

**Cost Anomaly:**

```
⚠️ Cost Anomaly Detected

Service: Amazon RDS
Cost: $1,200 today (300% above expected $400)
Reason: New db.r5.8xlarge instance launched

Action: Investigate RDS scaling event
```

**Savings Opportunity:**

```
💰 New Savings Recommendation

Type: Rightsizing
Resource: i-0abc123 (m5.2xlarge EC2 instance)
Current cost: $280/month
Recommended: m5.xlarge
Projected cost: $140/month
Savings: $140/month ($1,680/year)

Action: Review and approve in FinOps dashboard
```

______________________________________________________________________

## Benefits

### Cost Reduction

- **20-30% savings** from rightsizing and idle resource cleanup
- **15-40% savings** from Reserved Instance purchases
- **10-20% savings** from storage optimization

### Operational Efficiency

- **Real-time visibility** across AWS/GCP/Azure
- **Proactive alerts** prevent budget overruns
- **Automated recommendations** reduce manual analysis time

### Financial Accountability

- **Cost allocation** enables chargeback to teams
- **Budget tracking** enforces spending discipline
- **Trend analysis** supports capacity planning

______________________________________________________________________

## Alternatives Considered

### 1. Third-Party FinOps Tools

**CloudHealth by VMware:**

- ✅ Comprehensive multi-cloud support
- ✅ Advanced analytics and recommendations
- ❌ **Cost:** $5,000+/month for our scale
- ❌ Data sent to external SaaS (privacy concern)

**CloudZero:**

- ✅ Engineering-focused cost allocation
- ✅ Real-time anomaly detection
- ❌ **Cost:** $3,000+/month
- ❌ Limited customization

**Spot.io (formerly Spotinst):**

- ✅ Excellent Spot instance management
- ✅ Auto-scaling optimization
- ❌ **Scope:** Focus on compute only (not full FinOps)

**Decision:** Build in-house for full control, customization, and cost savings (~$500/month vs. $5,000/month).

### 2. Simple Spreadsheet Tracking

- ✅ Low cost (free)
- ❌ Manual, error-prone
- ❌ No real-time alerts
- ❌ No automation

**Decision:** Not scalable as infrastructure grows.

______________________________________________________________________

## Risks & Mitigation

| Risk                           | Impact                  | Mitigation                                         |
| ------------------------------ | ----------------------- | -------------------------------------------------- |
| **API rate limits**            | Cost data gaps          | Cache data, use 6h collection interval             |
| **Tag inconsistency**          | Poor cost allocation    | Enforce tagging policies via AWS Config/GCP Policy |
| **False positive anomalies**   | Alert fatigue           | ML model tuning, feedback loop                     |
| **Inaccurate recommendations** | Wasted engineering time | Validate with historical data, manual approval     |
| **Delayed cost data**          | Stale dashboards        | AWS/GCP have 24-48h delay (document limitation)    |

______________________________________________________________________

## Success Criteria

- [ ] Cost data collected from all 3 clouds (AWS, GCP, Azure)
- [ ] < 24h delay from cloud provider API to dashboard
- [ ] 95%+ accuracy in budget forecasts
- [ ] < 5% false positive rate for anomaly detection
- [ ] 20%+ cost reduction from implemented recommendations (first 6 months)
- [ ] 100% of resources tagged for cost allocation

______________________________________________________________________

## References

- [AWS Cost Explorer API](https://docs.aws.amazon.com/cost-management/latest/APIReference/Welcome.html)
- [GCP Billing API](https://cloud.google.com/billing/docs/apis)
- [Azure Cost Management API](https://docs.microsoft.com/en-us/rest/api/cost-management/)
- [FinOps Foundation Best Practices](https://www.finops.org/framework/)
- [TimescaleDB Time-Series](https://docs.timescale.com/)

______________________________________________________________________

**Status:** Ready for Implementation
**Next Steps:** Phase 1 - Cost Collection (AWS integration first)
