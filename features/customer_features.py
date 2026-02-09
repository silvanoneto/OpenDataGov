"""Customer feature definitions for Feast feature store.

These features are used for customer churn prediction and
customer lifetime value models.
"""

from datetime import timedelta

from feast import Entity, FeatureView, Field, FileSource
from feast.types import Float32, Float64, Int64, String

# ===== Entities =====

customer = Entity(
    name="customer_id",
    description="Customer unique identifier",
    join_keys=["customer_id"],
)

# ===== Feature Views =====

# Customer demographic features
customer_demographics = FeatureView(
    name="customer_demographics",
    description="Customer demographic information (age, income, location)",
    entities=[customer],
    ttl=timedelta(days=365),  # Demographics change slowly
    schema=[
        Field(name="age", dtype=Int64),
        Field(name="annual_income", dtype=Float64),
        Field(name="credit_score", dtype=Int64),
        Field(name="city", dtype=String),
        Field(name="state", dtype=String),
        Field(name="zip_code", dtype=String),
        Field(name="customer_since_days", dtype=Int64),
    ],
    online=True,  # Available for online serving
    source=FileSource(
        path="s3://feast-offline/customer_demographics.parquet",
        timestamp_field="event_timestamp",
    ),
    tags={
        "team": "data-science",
        "pii": "true",  # Contains PII - require governance approval
        "dq_required": "true",  # Require DQ validation
    },
)

# Customer transaction features (aggregated)
customer_transactions = FeatureView(
    name="customer_transactions",
    description="Aggregated customer transaction metrics (last 7/30/90 days)",
    entities=[customer],
    ttl=timedelta(days=1),  # Refresh daily
    schema=[
        Field(name="total_purchases_7d", dtype=Int64),
        Field(name="total_purchases_30d", dtype=Int64),
        Field(name="total_purchases_90d", dtype=Int64),
        Field(name="avg_order_value_7d", dtype=Float64),
        Field(name="avg_order_value_30d", dtype=Float64),
        Field(name="avg_order_value_90d", dtype=Float64),
        Field(name="days_since_last_purchase", dtype=Int64),
        Field(name="total_spend_7d", dtype=Float64),
        Field(name="total_spend_30d", dtype=Float64),
        Field(name="total_spend_90d", dtype=Float64),
    ],
    online=True,
    source=FileSource(
        path="s3://feast-offline/customer_transactions.parquet",
        timestamp_field="event_timestamp",
    ),
    tags={
        "team": "data-science",
        "freshness_sla": "24h",  # Must be < 24h old
        "dq_required": "true",
    },
)

# Customer engagement features
customer_engagement = FeatureView(
    name="customer_engagement",
    description="Customer engagement metrics (website visits, support tickets)",
    entities=[customer],
    ttl=timedelta(hours=6),  # Refresh every 6 hours
    schema=[
        Field(name="website_visits_7d", dtype=Int64),
        Field(name="website_visits_30d", dtype=Int64),
        Field(name="avg_session_duration_minutes", dtype=Float32),
        Field(name="support_tickets_30d", dtype=Int64),
        Field(name="support_tickets_resolved_30d", dtype=Int64),
        Field(name="email_open_rate_30d", dtype=Float32),
        Field(name="email_click_rate_30d", dtype=Float32),
    ],
    online=True,
    source=FileSource(
        path="s3://feast-offline/customer_engagement.parquet",
        timestamp_field="event_timestamp",
    ),
    tags={
        "team": "data-science",
        "freshness_sla": "6h",
    },
)

# Customer risk features (for fraud detection)
customer_risk = FeatureView(
    name="customer_risk",
    description="Customer risk indicators for fraud detection",
    entities=[customer],
    ttl=timedelta(hours=1),  # Refresh hourly (real-time risk)
    schema=[
        Field(name="failed_login_attempts_24h", dtype=Int64),
        Field(name="password_resets_30d", dtype=Int64),
        Field(name="returned_items_30d", dtype=Int64),
        Field(name="chargebacks_90d", dtype=Int64),
        Field(name="suspicious_activity_score", dtype=Float32),
        Field(name="account_age_days", dtype=Int64),
    ],
    online=True,
    source=FileSource(
        path="s3://feast-offline/customer_risk.parquet",
        timestamp_field="event_timestamp",
    ),
    tags={
        "team": "security",
        "freshness_sla": "1h",
        "governance_required": "true",  # HIGH risk features
    },
)
