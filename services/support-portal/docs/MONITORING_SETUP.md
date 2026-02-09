# Monitoring and Alerting Setup - Support Portal

**Version:** 1.0
**Last Updated:** 2026-02-08

______________________________________________________________________

## Overview

The Support Portal monitoring stack includes:

- **Prometheus**: Metrics collection and storage
- **Grafana**: Visualization and dashboards
- **Alertmanager**: Alert routing and notifications
- **CloudWatch/Datadog** (optional): Additional log aggregation

______________________________________________________________________

## Architecture

```
┌─────────────────┐
│  Support Portal │──┐
│  (FastAPI)      │  │ Metrics
└─────────────────┘  │ (Prometheus format)
                     │
┌─────────────────┐  │
│  PostgreSQL     │──┤
└─────────────────┘  │
                     │
┌─────────────────┐  │
│  Elasticsearch  │──┤
└─────────────────┘  │
                     │
                     ▼
              ┌─────────────┐
              │ Prometheus  │
              │  Server     │
              └─────────────┘
                     │
          ┌──────────┼──────────┐
          │                     │
    ┌───────────┐       ┌──────────────┐
    │  Grafana  │       │ Alertmanager │
    └───────────┘       └──────────────┘
          │                     │
          │                     ├─► PagerDuty
          │                     ├─► Slack
          │                     └─► Email
          ▼
    Dashboards
```

______________________________________________________________________

## 1. Prometheus Setup

### 1.1 Install Prometheus Operator

```bash
# Add Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install kube-prometheus-stack
helm install kube-prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.retention=30d \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=100Gi \
  --set alertmanager.enabled=true \
  --set grafana.enabled=true
```

### 1.2 Configure ServiceMonitor

```yaml
# servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: support-portal
  namespace: support-portal
  labels:
    app: support-portal
spec:
  selector:
    matchLabels:
      app: support-portal
  endpoints:
    - port: metrics
      interval: 30s
      path: /metrics
```

```bash
kubectl apply -f servicemonitor.yaml
```

### 1.3 Instrument Application

Add Prometheus instrumentation to FastAPI:

```python
# main.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
import time

# Metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

tickets_total = Gauge(
    'tickets_total',
    'Total tickets by status',
    ['status', 'priority']
)

sla_compliance_rate = Gauge(
    'sla_compliance_rate',
    'SLA compliance rate',
    ['support_tier']
)

# Middleware
class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        http_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()

        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)

        return response

app.add_middleware(PrometheusMiddleware)

# Metrics endpoint
@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

### 1.4 Apply Alert Rules

```bash
kubectl apply -f deploy/kubernetes/support-portal/prometheus-rules.yaml
```

______________________________________________________________________

## 2. Grafana Setup

### 2.1 Access Grafana

```bash
# Get admin password
kubectl get secret -n monitoring kube-prometheus-grafana \
  -o jsonpath="{.data.admin-password}" | base64 --decode

# Port forward
kubectl port-forward -n monitoring svc/kube-prometheus-grafana 3000:80

# Open browser
open http://localhost:3000
```

### 2.2 Import Dashboard

```bash
# Import support-portal.json dashboard
curl -X POST http://admin:$GRAFANA_PASSWORD@localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @deploy/docker-compose/grafana/dashboards/support-portal.json
```

### 2.3 Configure PostgreSQL Datasource

```bash
# Add PostgreSQL datasource
curl -X POST http://admin:$GRAFANA_PASSWORD@localhost:3000/api/datasources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "SupportPortal-PostgreSQL",
    "type": "postgres",
    "url": "'$DB_HOST':5432",
    "database": "support_portal",
    "user": "grafana_readonly",
    "secureJsonData": {
      "password": "'$GRAFANA_DB_PASSWORD'"
    },
    "jsonData": {
      "sslmode": "require",
      "maxOpenConns": 10,
      "maxIdleConns": 2
    }
  }'
```

### 2.4 Configure Elasticsearch Datasource

```bash
# Add Elasticsearch datasource
curl -X POST http://admin:$GRAFANA_PASSWORD@localhost:3000/api/datasources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "SupportPortal-Elasticsearch",
    "type": "elasticsearch",
    "url": "https://'$ES_ENDPOINT'",
    "database": "kb_articles",
    "basicAuth": true,
    "basicAuthUser": "elastic",
    "secureJsonData": {
      "basicAuthPassword": "'$ES_PASSWORD'"
    },
    "jsonData": {
      "esVersion": "8.0.0",
      "timeField": "@timestamp"
    }
  }'
```

______________________________________________________________________

## 3. Alertmanager Configuration

### 3.1 Configure Alert Routing

```yaml
# alertmanager-config.yaml
apiVersion: v1
kind: Secret
metadata:
  name: alertmanager-kube-prometheus-alertmanager
  namespace: monitoring
type: Opaque
stringData:
  alertmanager.yaml: |
    global:
      resolve_timeout: 5m
      slack_api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
      pagerduty_url: 'https://events.pagerduty.com/v2/enqueue'

    route:
      group_by: ['alertname', 'cluster', 'service']
      group_wait: 10s
      group_interval: 10s
      repeat_interval: 12h
      receiver: 'default'
      routes:
        # Critical alerts → PagerDuty + Slack
        - match:
            severity: critical
          receiver: 'pagerduty-critical'
          continue: true
        - match:
            severity: critical
          receiver: 'slack-critical'

        # Warning alerts → Slack only
        - match:
            severity: warning
          receiver: 'slack-warnings'

        # Info alerts → Slack low priority
        - match:
            severity: info
          receiver: 'slack-info'

    receivers:
      - name: 'default'
        email_configs:
          - to: 'eng-alerts@opendatagov.io'
            from: 'alertmanager@opendatagov.io'
            smarthost: 'smtp.sendgrid.net:587'
            auth_username: 'apikey'
            auth_password: '{{ .SENDGRID_API_KEY }}'

      - name: 'pagerduty-critical'
        pagerduty_configs:
          - routing_key: '{{ .PAGERDUTY_INTEGRATION_KEY }}'
            severity: 'critical'
            description: '{{ .CommonAnnotations.summary }}'
            details:
              firing: '{{ template "pagerduty.default.firing" . }}'
              resolved: '{{ template "pagerduty.default.resolved" . }}'

      - name: 'slack-critical'
        slack_configs:
          - channel: '#support-critical'
            title: '🚨 {{ .CommonAnnotations.summary }}'
            text: |
              *Alert:* {{ .CommonLabels.alertname }}
              *Severity:* {{ .CommonLabels.severity }}
              *Description:* {{ .CommonAnnotations.description }}
              *Runbook:* {{ .CommonAnnotations.runbook_url }}
              *Dashboard:* {{ .CommonAnnotations.dashboard_url }}
            color: 'danger'
            send_resolved: true

      - name: 'slack-warnings'
        slack_configs:
          - channel: '#support-alerts'
            title: '⚠️ {{ .CommonAnnotations.summary }}'
            text: '{{ .CommonAnnotations.description }}'
            color: 'warning'
            send_resolved: true

      - name: 'slack-info'
        slack_configs:
          - channel: '#support-metrics'
            title: 'ℹ️ {{ .CommonAnnotations.summary }}'
            text: '{{ .CommonAnnotations.description }}'
            color: 'good'
            send_resolved: false

    inhibit_rules:
      # Inhibit info alerts if critical alert is firing
      - source_match:
          severity: 'critical'
        target_match:
          severity: 'info'
        equal: ['alertname', 'service']

      # Inhibit warning if critical is firing
      - source_match:
          severity: 'critical'
        target_match:
          severity: 'warning'
        equal: ['alertname', 'service']
```

```bash
kubectl apply -f alertmanager-config.yaml
```

### 3.2 Test Alerting

```bash
# Trigger test alert
kubectl run alert-test --image=busybox --restart=Never -- \
  wget --post-data='[{"labels":{"alertname":"TestAlert","severity":"warning"}}]' \
  http://alertmanager-kube-prometheus-alertmanager.monitoring:9093/api/v1/alerts

# Check Slack #support-alerts for test alert
```

______________________________________________________________________

## 4. Log Aggregation

### Option A: CloudWatch Logs (AWS)

```bash
# Install Fluent Bit DaemonSet
kubectl apply -f https://raw.githubusercontent.com/aws-samples/amazon-cloudwatch-container-insights/latest/k8s-deployment-manifest-templates/deployment-mode/daemonset/container-insights-monitoring/fluent-bit/fluent-bit.yaml

# Configure log group
aws logs create-log-group --log-group-name /aws/eks/support-portal

# View logs
aws logs tail /aws/eks/support-portal/application --follow
```

### Option B: Datadog (Multi-Cloud)

```bash
# Install Datadog agent
helm install datadog-agent datadog/datadog \
  --namespace datadog \
  --create-namespace \
  --set datadog.apiKey=$DD_API_KEY \
  --set datadog.site=datadoghq.com \
  --set datadog.logs.enabled=true \
  --set datadog.logs.containerCollectAll=true \
  --set datadog.apm.enabled=true
```

### Option C: ELK Stack (Self-Hosted)

```bash
# Install Elastic Cloud on Kubernetes (ECK)
kubectl create -f https://download.elastic.co/downloads/eck/2.9.0/crds.yaml
kubectl apply -f https://download.elastic.co/downloads/eck/2.9.0/operator.yaml

# Deploy Elasticsearch cluster
kubectl apply -f - <<EOF
apiVersion: elasticsearch.k8s.elastic.co/v1
kind: Elasticsearch
metadata:
  name: support-portal-logs
  namespace: logging
spec:
  version: 8.11.0
  nodeSets:
    - name: default
      count: 3
      config:
        node.store.allow_mmap: false
EOF

# Deploy Kibana
kubectl apply -f - <<EOF
apiVersion: kibana.k8s.elastic.co/v1
kind: Kibana
metadata:
  name: support-portal-kibana
  namespace: logging
spec:
  version: 8.11.0
  count: 1
  elasticsearchRef:
    name: support-portal-logs
EOF
```

______________________________________________________________________

## 5. Synthetic Monitoring

### 5.1 Uptime Checks (Prometheus Blackbox Exporter)

```bash
# Install Blackbox Exporter
helm install blackbox-exporter prometheus-community/prometheus-blackbox-exporter \
  --namespace monitoring \
  --set config.modules.http_2xx.prober=http \
  --set config.modules.http_2xx.timeout=5s
```

```yaml
# blackbox-probe.yaml
apiVersion: monitoring.coreos.com/v1
kind: Probe
metadata:
  name: support-portal-uptime
  namespace: support-portal
spec:
  interval: 30s
  module: http_2xx
  targets:
    staticConfig:
      static:
        - https://support.opendatagov.io/api/health
        - https://support.opendatagov.io/api/v1/kb/search?q=test
```

```bash
kubectl apply -f blackbox-probe.yaml
```

### 5.2 End-to-End Tests (Synthetic Transactions)

```bash
# Create CronJob for E2E tests
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: CronJob
metadata:
  name: support-portal-e2e-test
  namespace: support-portal
spec:
  schedule: "*/15 * * * *"  # Every 15 minutes
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: e2e-test
              image: opendatagov/support-portal-e2e:latest
              env:
                - name: API_URL
                  value: https://support.opendatagov.io
                - name: TEST_EMAIL
                  value: e2e-test@opendatagov.io
              command:
                - python
                - scripts/e2e_test.py
          restartPolicy: OnFailure
EOF
```

______________________________________________________________________

## 6. Key Metrics to Monitor

### Application Metrics

| Metric                | Target | Alert Threshold |
| --------------------- | ------ | --------------- |
| Availability (uptime) | 99.9%  | < 99.5%         |
| P95 latency           | < 1s   | > 2s            |
| Error rate (5xx)      | < 1%   | > 5%            |
| Requests/second       | Varies | 2x baseline     |

### Business Metrics

| Metric                 | Target | Alert Threshold |
| ---------------------- | ------ | --------------- |
| SLA compliance         | > 95%  | < 80%           |
| Avg response time      | < 2h   | > 4h            |
| CSAT score             | > 4.0  | < 3.5           |
| Ticket resolution rate | > 80%  | < 70%           |

### Infrastructure Metrics

| Metric             | Target | Alert Threshold |
| ------------------ | ------ | --------------- |
| Pod CPU usage      | < 70%  | > 90%           |
| Pod memory usage   | < 80%  | > 90%           |
| DB connection pool | < 80%  | > 90%           |
| Disk usage         | < 75%  | > 85%           |

______________________________________________________________________

## 7. Dashboard URLs

Once deployed:

- **Grafana:** https://grafana.opendatagov.io/d/support-portal
- **Prometheus:** http://prometheus.opendatagov.io:9090
- **Alertmanager:** http://alertmanager.opendatagov.io:9093
- **Kibana (if ELK):** https://kibana.opendatagov.io

______________________________________________________________________

## 8. On-Call Setup

### 8.1 Configure PagerDuty Escalation Policy

1. **Level 1:** On-call engineer (notify immediately)
1. **Level 2:** Senior engineer (escalate after 15 minutes)
1. **Level 3:** Engineering manager (escalate after 30 minutes)

### 8.2 On-Call Rotation

```
Week 1: Engineer A
Week 2: Engineer B
Week 3: Engineer C
Week 4: Engineer D
```

### 8.3 On-Call Playbook

**When You Get Paged:**

1. **Acknowledge** alert in PagerDuty (< 5 minutes)
1. **Assess** severity (P1/P2/P3)
1. **Follow runbook** (link in PagerDuty alert)
1. **Update** status page if customer-facing
1. **Communicate** progress in Slack #incidents
1. **Resolve** incident
1. **Write** post-mortem (P1 incidents only)

______________________________________________________________________

## 9. Status Page

### Setup Status Page (Statuspage.io)

```bash
# Create Statuspage via API
curl -X POST https://api.statuspage.io/v1/pages \
  -H "Authorization: OAuth $STATUSPAGE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "page": {
      "name": "OpenDataGov Support Portal",
      "subdomain": "status-support",
      "url": "https://status-support.opendatagov.io"
    }
  }'

# Add components
curl -X POST https://api.statuspage.io/v1/pages/$PAGE_ID/components \
  -H "Authorization: OAuth $STATUSPAGE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "component": {
      "name": "Support Portal API",
      "status": "operational"
    }
  }'
```

### Automate Status Updates

```python
# Update status on incident
import requests

def update_status_page(component_id, status, message):
    """Update Statuspage component status."""
    url = f"https://api.statuspage.io/v1/pages/{PAGE_ID}/components/{component_id}"
    headers = {"Authorization": f"OAuth {STATUSPAGE_API_KEY}"}

    payload = {
        "component": {
            "status": status  # operational, degraded_performance, partial_outage, major_outage
        }
    }

    response = requests.patch(url, json=payload, headers=headers)

    # Post incident update
    if status != "operational":
        incident_url = f"https://api.statuspage.io/v1/pages/{PAGE_ID}/incidents"
        incident_payload = {
            "incident": {
                "name": message,
                "status": "investigating",
                "impact": "major" if "major_outage" in status else "minor",
                "component_ids": [component_id]
            }
        }
        requests.post(incident_url, json=incident_payload, headers=headers)
```

______________________________________________________________________

## 10. Verification Checklist

- [ ] Prometheus scraping metrics from all pods
- [ ] Grafana dashboards showing live data
- [ ] Alertmanager receiving test alerts
- [ ] PagerDuty integration working (test page sent)
- [ ] Slack notifications arriving in correct channels
- [ ] Logs aggregating in CloudWatch/Datadog/ELK
- [ ] Uptime checks running every 30s
- [ ] E2E tests passing every 15 minutes
- [ ] Status page configured and accessible
- [ ] On-call rotation configured in PagerDuty
- [ ] Runbooks linked from alert annotations

______________________________________________________________________

**Monitoring Setup Completed By:** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
**Date:** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
**Next Review:** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
