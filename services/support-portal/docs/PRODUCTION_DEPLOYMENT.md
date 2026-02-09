# Production Deployment Guide - Support Portal

**Version:** 1.0
**Last Updated:** 2026-02-08
**Target Environment:** Kubernetes (AWS EKS / GCP GKE / Azure AKS)

______________________________________________________________________

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
1. [Infrastructure Setup](#infrastructure-setup)
1. [Database Migration](#database-migration)
1. [Secrets Configuration](#secrets-configuration)
1. [Deployment Steps](#deployment-steps)
1. [Post-Deployment Verification](#post-deployment-verification)
1. [Rollback Procedure](#rollback-procedure)
1. [Troubleshooting](#troubleshooting)

______________________________________________________________________

## Pre-Deployment Checklist

### ✅ Code Quality

- [ ] All tests passing (`pytest services/support-portal/tests/ -v`)
- [ ] Code coverage ≥ 80% (`pytest --cov`)
- [ ] Linting passes (`flake8 services/support-portal/`)
- [ ] Security scan clean (`bandit -r services/support-portal/src/`)
- [ ] Dependency vulnerabilities resolved (`safety check`)

### ✅ Documentation

- [ ] API documentation updated (OpenAPI/Swagger)
- [ ] Architecture Decision Records (ADRs) written
- [ ] Runbooks created for common incidents
- [ ] Release notes drafted

### ✅ Infrastructure

- [ ] Kubernetes cluster provisioned (EKS/GKE/AKS)
- [ ] PostgreSQL RDS instance created (Multi-AZ, encrypted)
- [ ] Elasticsearch cluster configured (3 nodes minimum)
- [ ] Redis cluster configured (replication enabled)
- [ ] Load balancer configured with TLS certificate
- [ ] DNS records updated (support.opendatagov.io)

### ✅ External Integrations

- [ ] SendGrid account verified (sender domain authenticated)
- [ ] Slack workspace configured (bot created, channels set up)
- [ ] PagerDuty service created (escalation policy configured)
- [ ] Jira project created (issue types, workflows configured)
- [ ] Zendesk integration tested (bidirectional sync working)

### ✅ Monitoring

- [ ] Grafana dashboards imported
- [ ] Prometheus scraping configured
- [ ] CloudWatch/Datadog/New Relic integration enabled
- [ ] Alerting rules configured
- [ ] On-call rotation configured in PagerDuty

______________________________________________________________________

## Infrastructure Setup

### 1. Kubernetes Namespace

```bash
kubectl create namespace support-portal
kubectl label namespace support-portal environment=production
```

### 2. PostgreSQL RDS (AWS Example)

```bash
aws rds create-db-instance \
  --db-instance-identifier odg-support-portal-prod \
  --db-instance-class db.r5.xlarge \
  --engine postgres \
  --engine-version 15.3 \
  --master-username odg_admin \
  --master-user-password <SECURE_PASSWORD> \
  --allocated-storage 100 \
  --storage-type gp3 \
  --storage-encrypted \
  --multi-az \
  --vpc-security-group-ids sg-xxx \
  --db-subnet-group-name odg-db-subnet-group \
  --backup-retention-period 30 \
  --preferred-backup-window "03:00-04:00" \
  --preferred-maintenance-window "sun:04:00-sun:05:00" \
  --tags Key=Environment,Value=production Key=Service,Value=support-portal
```

**Post-Creation:**

```bash
# Get endpoint
export DB_HOST=$(aws rds describe-db-instances \
  --db-instance-identifier odg-support-portal-prod \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text)

echo "DB_HOST=$DB_HOST"
```

### 3. Elasticsearch (AWS OpenSearch Example)

```bash
aws opensearch create-domain \
  --domain-name odg-support-kb-prod \
  --engine-version OpenSearch_2.9 \
  --cluster-config \
    InstanceType=r6g.large.search,InstanceCount=3,DedicatedMasterEnabled=true,DedicatedMasterType=r6g.large.search,DedicatedMasterCount=3 \
  --ebs-options EBSEnabled=true,VolumeType=gp3,VolumeSize=100 \
  --encryption-at-rest-options Enabled=true \
  --node-to-node-encryption-options Enabled=true \
  --access-policies file://opensearch-access-policy.json \
  --vpc-options SubnetIds=subnet-xxx,SecurityGroupIds=sg-xxx
```

### 4. Redis (AWS ElastiCache Example)

```bash
aws elasticache create-replication-group \
  --replication-group-id odg-support-cache-prod \
  --replication-group-description "Support Portal Cache" \
  --engine redis \
  --engine-version 7.0 \
  --cache-node-type cache.r6g.large \
  --num-cache-clusters 3 \
  --automatic-failover-enabled \
  --at-rest-encryption-enabled \
  --transit-encryption-enabled \
  --cache-subnet-group-name odg-cache-subnet-group \
  --security-group-ids sg-xxx
```

______________________________________________________________________

## Database Migration

### 1. Backup Existing Database (if upgrading)

```bash
# Create backup
pg_dump -h $DB_HOST -U odg_admin -d support_portal -F c -b -v -f backup_$(date +%Y%m%d_%H%M%S).dump

# Verify backup
pg_restore --list backup_*.dump | head -20
```

### 2. Run Migrations

```bash
# Connect to bastion host
ssh -i ~/.ssh/odg-prod.pem ubuntu@bastion.opendatagov.io

# Clone repo
git clone https://github.com/opendatagov/opendatagov.git
cd opendatagov/services/support-portal

# Set environment
export DATABASE_URL="postgresql://odg_admin:${DB_PASSWORD}@${DB_HOST}:5432/support_portal"

# Run migrations
alembic upgrade head

# Verify tables created
psql $DATABASE_URL -c "\dt"
```

### 3. Seed Initial Data

```bash
# Create initial KB articles
python scripts/seed_knowledge_base.py

# Create default organizations
python scripts/seed_organizations.py

# Create staff accounts
python scripts/create_staff_users.py
```

______________________________________________________________________

## Secrets Configuration

### 1. Create Kubernetes Secrets

```bash
# Database credentials
kubectl create secret generic support-portal-db \
  --from-literal=DATABASE_URL="postgresql://odg_admin:${DB_PASSWORD}@${DB_HOST}:5432/support_portal" \
  -n support-portal

# SendGrid
kubectl create secret generic support-portal-sendgrid \
  --from-literal=SENDGRID_API_KEY="${SENDGRID_API_KEY}" \
  --from-literal=SENDGRID_FROM_EMAIL="support@opendatagov.io" \
  -n support-portal

# Slack
kubectl create secret generic support-portal-slack \
  --from-literal=SLACK_BOT_TOKEN="${SLACK_BOT_TOKEN}" \
  --from-literal=SLACK_SIGNING_SECRET="${SLACK_SIGNING_SECRET}" \
  -n support-portal

# PagerDuty
kubectl create secret generic support-portal-pagerduty \
  --from-literal=PAGERDUTY_API_TOKEN="${PAGERDUTY_API_TOKEN}" \
  --from-literal=PAGERDUTY_INTEGRATION_KEY="${PAGERDUTY_INTEGRATION_KEY}" \
  --from-literal=PAGERDUTY_ESCALATION_POLICY_ID="${PAGERDUTY_ESCALATION_POLICY_ID}" \
  -n support-portal

# Jira
kubectl create secret generic support-portal-jira \
  --from-literal=JIRA_URL="https://opendatagov.atlassian.net" \
  --from-literal=JIRA_EMAIL="${JIRA_EMAIL}" \
  --from-literal=JIRA_API_TOKEN="${JIRA_API_TOKEN}" \
  -n support-portal

# Zendesk
kubectl create secret generic support-portal-zendesk \
  --from-literal=ZENDESK_SUBDOMAIN="opendatagov" \
  --from-literal=ZENDESK_EMAIL="${ZENDESK_EMAIL}" \
  --from-literal=ZENDESK_API_TOKEN="${ZENDESK_API_TOKEN}" \
  -n support-portal

# JWT Secret
kubectl create secret generic support-portal-jwt \
  --from-literal=JWT_SECRET_KEY="$(openssl rand -base64 64)" \
  --from-literal=JWT_ALGORITHM="HS256" \
  -n support-portal
```

### 2. Verify Secrets

```bash
kubectl get secrets -n support-portal
kubectl describe secret support-portal-db -n support-portal
```

______________________________________________________________________

## Deployment Steps

### 1. Build and Push Docker Image

```bash
# Build image
cd services/support-portal
docker build -t opendatagov/support-portal:v1.0.0 .

# Tag for registry
docker tag opendatagov/support-portal:v1.0.0 \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/opendatagov/support-portal:v1.0.0

# Push to ECR/GCR/ACR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/opendatagov/support-portal:v1.0.0
```

### 2. Deploy with Helm

```bash
# Add Helm repo
helm repo add opendatagov https://helm.opendatagov.io
helm repo update

# Install/Upgrade
helm upgrade --install support-portal opendatagov/support-portal \
  --namespace support-portal \
  --create-namespace \
  --values values-production.yaml \
  --set image.tag=v1.0.0 \
  --set replicaCount=3 \
  --set resources.requests.cpu=1 \
  --set resources.requests.memory=2Gi \
  --set resources.limits.cpu=2 \
  --set resources.limits.memory=4Gi \
  --set autoscaling.enabled=true \
  --set autoscaling.minReplicas=3 \
  --set autoscaling.maxReplicas=10 \
  --set autoscaling.targetCPUUtilizationPercentage=70 \
  --wait \
  --timeout 10m
```

### 3. Deploy Frontend (Next.js)

```bash
cd services/support-portal/frontend

# Build
npm run build

# Deploy to Vercel/Netlify
vercel --prod

# Or deploy to S3 + CloudFront
aws s3 sync out/ s3://support-portal-frontend-prod/ --delete
aws cloudfront create-invalidation --distribution-id E123456 --paths "/*"
```

### 4. Configure Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: support-portal
  namespace: support-portal
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  tls:
    - hosts:
        - support.opendatagov.io
      secretName: support-portal-tls
  rules:
    - host: support.opendatagov.io
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: support-portal
                port:
                  number: 8000
          - path: /
            pathType: Prefix
            backend:
              service:
                name: support-portal-frontend
                port:
                  number: 3000
```

```bash
kubectl apply -f ingress.yaml
```

______________________________________________________________________

## Post-Deployment Verification

### 1. Health Checks

```bash
# Check pods
kubectl get pods -n support-portal
kubectl logs -f deployment/support-portal -n support-portal

# Check services
kubectl get svc -n support-portal

# Check ingress
kubectl get ingress -n support-portal
```

### 2. API Smoke Tests

```bash
# Health endpoint
curl https://support.opendatagov.io/api/health
# Expected: {"status": "healthy", "version": "1.0.0"}

# Create test ticket
curl -X POST https://support.opendatagov.io/api/v1/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Production deployment test",
    "description": "Testing post-deployment",
    "customer_name": "Test User",
    "customer_email": "test@opendatagov.io",
    "priority": "P4_LOW"
  }'

# Search KB
curl "https://support.opendatagov.io/api/v1/kb/search?q=test"
```

### 3. Integration Tests

```bash
# Test SendGrid (check inbox for test email)
python scripts/test_sendgrid_integration.py

# Test Slack (check #support-test channel)
python scripts/test_slack_integration.py

# Test PagerDuty (check incidents)
python scripts/test_pagerduty_integration.py
```

### 4. Load Test

```bash
# Run Locust load test (1 minute, 100 users)
locust -f tests/load_test_locust.py \
  --host=https://support.opendatagov.io \
  --users=100 \
  --spawn-rate=10 \
  --run-time=60s \
  --headless
```

### 5. Monitoring Verification

```bash
# Check Grafana dashboards
open https://grafana.opendatagov.io/d/support-portal

# Verify Prometheus metrics
curl http://support-portal-prometheus:9090/api/v1/query?query=up{job="support-portal"}

# Check CloudWatch logs
aws logs tail /aws/eks/support-portal/application --follow
```

______________________________________________________________________

## Rollback Procedure

### Scenario 1: Recent Deployment (< 1 hour ago)

```bash
# Rollback Helm release
helm rollback support-portal -n support-portal

# Verify rollback
kubectl get pods -n support-portal
kubectl logs -f deployment/support-portal -n support-portal

# Check API health
curl https://support.opendatagov.io/api/health
```

### Scenario 2: Database Migration Issue

```bash
# Connect to database
psql $DATABASE_URL

# Rollback migration (one version)
alembic downgrade -1

# Or rollback to specific version
alembic downgrade <revision_id>

# Verify schema
\dt
```

### Scenario 3: Critical Bug in Production

```bash
# Deploy previous stable version
helm upgrade support-portal opendatagov/support-portal \
  --namespace support-portal \
  --set image.tag=v0.9.5 \  # Previous stable version
  --wait \
  --timeout 5m

# Enable maintenance mode (503 Service Unavailable)
kubectl scale deployment support-portal --replicas=0 -n support-portal
kubectl apply -f maintenance-mode.yaml

# Fix bug, test in staging, re-deploy
```

### Scenario 4: Database Corruption

```bash
# Stop application
kubectl scale deployment support-portal --replicas=0 -n support-portal

# Restore from backup
pg_restore -h $DB_HOST -U odg_admin -d support_portal -c backup_20260208_030000.dump

# Verify data
psql $DATABASE_URL -c "SELECT COUNT(*) FROM tickets;"

# Restart application
kubectl scale deployment support-portal --replicas=3 -n support-portal
```

______________________________________________________________________

## Troubleshooting

### Issue 1: Pods Crashing (CrashLoopBackOff)

```bash
# Check pod logs
kubectl logs -f <pod-name> -n support-portal

# Describe pod for events
kubectl describe pod <pod-name> -n support-portal

# Common causes:
# - Missing environment variables
# - Database connection failure
# - OOM (Out of Memory)

# Fix: Check secrets and resource limits
kubectl get secret support-portal-db -n support-portal -o yaml
kubectl top pod -n support-portal
```

### Issue 2: Database Connection Timeout

```bash
# Test database connectivity from pod
kubectl run -it --rm debug --image=postgres:15 --restart=Never -n support-portal -- \
  psql -h $DB_HOST -U odg_admin -d support_portal

# Check security groups (AWS)
aws ec2 describe-security-groups --group-ids sg-xxx

# Verify RDS is accessible
aws rds describe-db-instances --db-instance-identifier odg-support-portal-prod
```

### Issue 3: High Latency (P95 > 1s)

```bash
# Check resource utilization
kubectl top pods -n support-portal

# Scale horizontally
kubectl scale deployment support-portal --replicas=10 -n support-portal

# Check database performance
psql $DATABASE_URL -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"

# Add database indexes (if needed)
psql $DATABASE_URL -c "CREATE INDEX idx_tickets_status ON tickets(status);"
```

### Issue 4: SLA Breach Alerts Not Firing

```bash
# Check background job logs
kubectl logs -f deployment/support-portal -n support-portal | grep "sla_monitor"

# Verify cron job is running
kubectl get cronjobs -n support-portal
kubectl get jobs -n support-portal

# Manually trigger SLA check
kubectl create job --from=cronjob/sla-monitor sla-monitor-manual -n support-portal
```

### Issue 5: Elasticsearch Search Not Working

```bash
# Check Elasticsearch health
curl -u elastic:$ES_PASSWORD https://$ES_ENDPOINT/_cluster/health

# Verify index exists
curl -u elastic:$ES_PASSWORD https://$ES_ENDPOINT/_cat/indices?v

# Reindex KB articles
python scripts/reindex_knowledge_base.py

# Test search directly
curl -u elastic:$ES_PASSWORD -X GET "https://$ES_ENDPOINT/kb_articles/_search" \
  -H 'Content-Type: application/json' \
  -d '{"query": {"match": {"content": "test"}}}'
```

______________________________________________________________________

## Maintenance Windows

### Scheduled Maintenance: Sundays 02:00-04:00 UTC

**Pre-Maintenance:**

1. Send customer notification email (72 hours advance notice)
1. Post banner on support portal
1. Update status page (status.opendatagov.io)

**During Maintenance:**

1. Enable maintenance mode
1. Perform updates (OS patches, database maintenance, etc.)
1. Run smoke tests
1. Disable maintenance mode

**Post-Maintenance:**

1. Verify all services operational
1. Send "all clear" notification
1. Update status page

______________________________________________________________________

## Emergency Contacts

**On-Call Engineer:** PagerDuty escalation policy
**Database Admin:** dba@opendatagov.io
**Security Team:** security@opendatagov.io
**Management:** eng-leadership@opendatagov.io

**External Vendors:**

- **AWS Support:** Premium support (15-minute response)
- **SendGrid Support:** support@sendgrid.com
- **Slack Support:** Slack workspace admins

______________________________________________________________________

## Post-Deployment Checklist

- [ ] All pods running and healthy
- [ ] API smoke tests passing
- [ ] Load test completed successfully
- [ ] Monitoring dashboards showing metrics
- [ ] Alerts configured and tested
- [ ] Backup jobs running
- [ ] Documentation updated
- [ ] Team notified of deployment
- [ ] Customer announcement sent (if applicable)
- [ ] Post-deployment review scheduled (within 1 week)

______________________________________________________________________

**Deployment Completed By:** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
**Date:** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
**Version Deployed:** v1.0.0
**Rollback Plan Verified:** ☑ Yes
