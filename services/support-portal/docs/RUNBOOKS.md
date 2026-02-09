# Support Portal Runbooks

**Version:** 1.0
**Last Updated:** 2026-02-08

______________________________________________________________________

## Table of Contents

1. [Service Down / 503 Errors](#runbook-1-service-down--503-errors)
1. [Database Connection Pool Exhausted](#runbook-2-database-connection-pool-exhausted)
1. [SLA Breach Storm (Multiple Breaches)](#runbook-3-sla-breach-storm)
1. [Elasticsearch Index Corruption](#runbook-4-elasticsearch-index-corruption)
1. [High Memory Usage / OOM Kills](#runbook-5-high-memory-usage--oom-kills)
1. [External Integration Failure](#runbook-6-external-integration-failure)
1. [Spam Ticket Attack](#runbook-7-spam-ticket-attack)
1. [Database Migration Failure](#runbook-8-database-migration-failure)
1. [TLS Certificate Expiring](#runbook-9-tls-certificate-expiring)
1. [Sudden Traffic Spike / DDoS](#runbook-10-sudden-traffic-spike--ddos)

______________________________________________________________________

## Runbook 1: Service Down / 503 Errors

### Symptoms

- Users reporting "Service Unavailable"
- HTTP 503 responses
- PagerDuty alert: "Support Portal Down"
- Grafana: 0 healthy pods

### Severity: **P1 CRITICAL**

**Response Time:** 15 minutes
**Resolution Time:** 1 hour

### Investigation Steps

```bash
# 1. Check pod status
kubectl get pods -n support-portal

# 2. Check recent deployments
kubectl rollout history deployment/support-portal -n support-portal

# 3. Check pod logs for errors
kubectl logs -f deployment/support-portal -n support-portal --tail=100

# 4. Describe failed pod
FAILED_POD=$(kubectl get pods -n support-portal | grep -E '(CrashLoopBackOff|Error)' | awk '{print $1}' | head -1)
kubectl describe pod $FAILED_POD -n support-portal

# 5. Check events
kubectl get events -n support-portal --sort-by='.lastTimestamp' | tail -20
```

### Common Causes & Fixes

#### Cause 1: Missing Environment Variables

```bash
# Verify secrets exist
kubectl get secrets -n support-portal

# Check if secret is mounted
kubectl get pod <pod-name> -n support-portal -o yaml | grep -A 5 envFrom

# Fix: Recreate missing secret
kubectl create secret generic support-portal-db \
  --from-literal=DATABASE_URL="postgresql://..." \
  -n support-portal

# Restart pods
kubectl rollout restart deployment/support-portal -n support-portal
```

#### Cause 2: Database Unreachable

```bash
# Test database connection from pod
kubectl run -it --rm db-test --image=postgres:15 --restart=Never -n support-portal -- \
  psql -h $DB_HOST -U odg_admin -d support_portal -c "SELECT 1;"

# If fails: Check RDS status
aws rds describe-db-instances --db-instance-identifier odg-support-portal-prod

# Check security group allows traffic
aws ec2 describe-security-groups --group-ids sg-xxx --query 'SecurityGroups[0].IpPermissions'
```

#### Cause 3: Image Pull Error

```bash
# Check image pull secrets
kubectl get secrets -n support-portal | grep regcred

# Create if missing
kubectl create secret docker-registry regcred \
  --docker-server=123456789012.dkr.ecr.us-east-1.amazonaws.com \
  --docker-username=AWS \
  --docker-password=$(aws ecr get-login-password --region us-east-1) \
  -n support-portal

# Patch deployment to use secret
kubectl patch deployment support-portal -n support-portal \
  -p '{"spec":{"template":{"spec":{"imagePullSecrets":[{"name":"regcred"}]}}}}'
```

### Mitigation

```bash
# Quick rollback to last known good version
helm rollback support-portal -n support-portal

# OR scale down and enable maintenance mode
kubectl scale deployment support-portal --replicas=0 -n support-portal
kubectl apply -f maintenance-mode.yaml
```

### Post-Incident

- [ ] Update status page
- [ ] Send customer notification
- [ ] Schedule post-mortem
- [ ] Update monitoring alerts

______________________________________________________________________

## Runbook 2: Database Connection Pool Exhausted

### Symptoms

- Errors: "FATAL: remaining connection slots are reserved"
- Slow response times (P95 > 5s)
- Grafana: PostgreSQL connections at max

### Severity: **P1 CRITICAL**

### Investigation Steps

```bash
# 1. Check active connections
psql $DATABASE_URL -c "
SELECT
  count(*),
  state,
  application_name
FROM pg_stat_activity
WHERE datname = 'support_portal'
GROUP BY state, application_name;
"

# 2. Find long-running queries
psql $DATABASE_URL -c "
SELECT
  pid,
  now() - query_start AS duration,
  state,
  query
FROM pg_stat_activity
WHERE state != 'idle'
AND query_start < now() - interval '5 minutes'
ORDER BY duration DESC;
"

# 3. Check connection pool settings
kubectl exec -it deployment/support-portal -n support-portal -- \
  python -c "from sqlalchemy import create_engine; print(create_engine('$DATABASE_URL').pool.size())"
```

### Resolution

#### Option 1: Increase Pool Size (Quick Fix)

```bash
# Update deployment with larger pool
kubectl set env deployment/support-portal -n support-portal \
  DB_POOL_SIZE=50 \
  DB_MAX_OVERFLOW=10

# Restart pods
kubectl rollout restart deployment/support-portal -n support-portal
```

#### Option 2: Kill Idle Connections

```bash
# Kill connections idle > 10 minutes
psql $DATABASE_URL -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'support_portal'
AND state = 'idle'
AND state_change < now() - interval '10 minutes';
"
```

#### Option 3: Scale RDS Instance (if needed)

```bash
# Modify RDS instance class
aws rds modify-db-instance \
  --db-instance-identifier odg-support-portal-prod \
  --db-instance-class db.r5.2xlarge \
  --apply-immediately
```

### Prevention

- [ ] Set connection pool limits: `pool_size=20, max_overflow=5`
- [ ] Add connection timeout: `pool_timeout=30`
- [ ] Enable connection recycling: `pool_recycle=3600`
- [ ] Monitor connection usage (alert at 80%)

______________________________________________________________________

## Runbook 3: SLA Breach Storm

### Symptoms

- PagerDuty: 50+ SLA breach alerts in 10 minutes
- Slack: #support-critical channel flooded with breach notifications
- Grafana: SLA compliance drops below 70%

### Severity: **P2 HIGH**

### Investigation Steps

```bash
# 1. Count breached tickets
psql $DATABASE_URL -c "
SELECT
  priority,
  COUNT(*) as breached_count
FROM tickets
WHERE status IN ('OPEN', 'IN_PROGRESS')
AND (
  first_response_at IS NULL AND NOW() > response_sla_target
  OR resolved_at IS NULL AND NOW() > resolution_sla_target
)
GROUP BY priority;
"

# 2. Check agent availability
psql $DATABASE_URL -c "
SELECT
  COUNT(DISTINCT assigned_to) as active_agents,
  COUNT(*) as assigned_tickets
FROM tickets
WHERE status = 'OPEN' AND assigned_to IS NOT NULL;
"

# 3. Check for system outage
kubectl logs -f deployment/support-portal -n support-portal --tail=100 | grep -i error
```

### Root Cause Analysis

#### Cause 1: Agent Shortage (Understaffing)

```bash
# Check current workload
psql $DATABASE_URL -c "
SELECT
  assigned_to,
  COUNT(*) as ticket_count
FROM tickets
WHERE status IN ('OPEN', 'IN_PROGRESS')
GROUP BY assigned_to
ORDER BY ticket_count DESC;
"

# Fix: Enable auto-assignment for unassigned tickets
python scripts/bulk_assign_tickets.py --strategy load_balanced
```

#### Cause 2: High Ticket Volume (Incident Affecting Many Customers)

```bash
# Check for duplicate issues
psql $DATABASE_URL -c "
SELECT
  subject,
  COUNT(*) as ticket_count
FROM tickets
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY subject
HAVING COUNT(*) > 5
ORDER BY ticket_count DESC;
"

# Fix: Create KB article, send proactive email to all affected customers
```

#### Cause 3: SLA Monitoring System Down

```bash
# Check cron job status
kubectl get cronjobs -n support-portal
kubectl logs job/sla-monitor-<timestamp> -n support-portal

# Fix: Manually trigger SLA check
kubectl create job --from=cronjob/sla-monitor sla-monitor-manual -n support-portal
```

### Triage Actions

```bash
# 1. Prioritize P1 CRITICAL tickets
psql $DATABASE_URL -c "
UPDATE tickets
SET priority = 'P1_CRITICAL'
WHERE subject ILIKE '%production%' OR subject ILIKE '%down%'
AND status = 'OPEN';
"

# 2. Send bulk update to customers
python scripts/send_bulk_notification.py \
  --subject "We're experiencing high support volume" \
  --message "Response times may be longer than usual. ETA: 4 hours"

# 3. Escalate to management
python scripts/notify_sla_breach_storm.py --count 50 --recipients eng-leadership@opendatagov.io
```

### Post-Incident

- [ ] Analyze breach patterns
- [ ] Adjust SLA targets if consistently unrealistic
- [ ] Hire additional support staff
- [ ] Improve KB articles to reduce ticket volume

______________________________________________________________________

## Runbook 4: Elasticsearch Index Corruption

### Symptoms

- KB search returns 0 results
- Elasticsearch logs: "IndexCorruptionException"
- API errors: "Elasticsearch connection failed"

### Severity: **P2 HIGH**

### Investigation Steps

```bash
# 1. Check Elasticsearch cluster health
curl -u elastic:$ES_PASSWORD https://$ES_ENDPOINT/_cluster/health

# 2. Check index status
curl -u elastic:$ES_PASSWORD https://$ES_ENDPOINT/_cat/indices/kb_articles?v

# 3. Check shard allocation
curl -u elastic:$ES_PASSWORD https://$ES_ENDPOINT/_cat/shards/kb_articles?v
```

### Resolution

#### Option 1: Force Merge (if red shards)

```bash
curl -X POST -u elastic:$ES_PASSWORD \
  "https://$ES_ENDPOINT/kb_articles/_forcemerge?max_num_segments=1"
```

#### Option 2: Delete and Recreate Index

```bash
# 1. Delete corrupted index
curl -X DELETE -u elastic:$ES_PASSWORD \
  https://$ES_ENDPOINT/kb_articles

# 2. Recreate index with mapping
python scripts/create_elasticsearch_index.py

# 3. Reindex all KB articles from PostgreSQL
python scripts/reindex_knowledge_base.py

# 4. Verify search works
curl -u elastic:$ES_PASSWORD -X GET \
  "https://$ES_ENDPOINT/kb_articles/_search?q=test"
```

#### Option 3: Restore from Snapshot (if available)

```bash
# List snapshots
curl -u elastic:$ES_PASSWORD \
  https://$ES_ENDPOINT/_snapshot/kb_backup/_all

# Restore latest snapshot
curl -X POST -u elastic:$ES_PASSWORD \
  "https://$ES_ENDPOINT/_snapshot/kb_backup/snapshot_20260208/_restore" \
  -H 'Content-Type: application/json' \
  -d '{"indices": "kb_articles"}'
```

### Prevention

- [ ] Enable daily Elasticsearch snapshots
- [ ] Monitor disk space (alert at 80%)
- [ ] Configure index lifecycle management (ILM)

______________________________________________________________________

## Runbook 5: High Memory Usage / OOM Kills

### Symptoms

- Pods restarting frequently
- Grafana: Memory usage > 90%
- Kubernetes events: "OOMKilled"

### Severity: **P2 HIGH**

### Investigation Steps

```bash
# 1. Check memory usage
kubectl top pods -n support-portal

# 2. Check OOMKilled events
kubectl get events -n support-portal | grep OOMKilled

# 3. Check memory limits
kubectl get deployment support-portal -n support-portal -o yaml | grep -A 5 resources

# 4. Profile application memory
kubectl exec -it deployment/support-portal -n support-portal -- \
  python -c "import objgraph; objgraph.show_most_common_types(limit=20)"
```

### Resolution

#### Quick Fix: Increase Memory Limits

```bash
kubectl set resources deployment/support-portal -n support-portal \
  --limits=memory=4Gi \
  --requests=memory=2Gi

kubectl rollout restart deployment/support-portal -n support-portal
```

#### Root Cause Fixes

**Memory Leak in Application:**

```bash
# Enable memory profiling
kubectl set env deployment/support-portal -n support-portal \
  PYTHONTRACEMALLOC=1

# Analyze with memory_profiler
kubectl exec -it deployment/support-portal -n support-portal -- \
  python -m memory_profiler main.py
```

**Large Query Results:**

```bash
# Add pagination to large queries
psql $DATABASE_URL -c "
SELECT pg_stat_statements.query,
       pg_stat_statements.calls,
       pg_stat_statements.mean_exec_time,
       pg_stat_statements.max_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
"
```

______________________________________________________________________

## Runbook 6: External Integration Failure

### Symptoms

- SendGrid: Emails not sending
- Slack: Notifications not appearing
- PagerDuty: Incidents not creating
- Jira: Issues not syncing

### Severity: **P3 NORMAL** (unless SendGrid down for CSAT = P2)

### Investigation Steps

```bash
# 1. Check integration logs
kubectl logs -f deployment/support-portal -n support-portal | grep -E "(sendgrid|slack|pagerduty|jira)"

# 2. Test integration endpoints
python scripts/test_integrations.py

# 3. Check API key validity
curl -H "Authorization: Bearer $SENDGRID_API_KEY" https://api.sendgrid.com/v3/user/profile
curl -H "Authorization: Bearer $SLACK_BOT_TOKEN" https://slack.com/api/auth.test
```

### Resolution

#### SendGrid Down

```bash
# Check SendGrid status
curl https://status.sendgrid.com/api/v2/status.json

# Fallback: Use SES
kubectl set env deployment/support-portal -n support-portal \
  EMAIL_PROVIDER=ses \
  AWS_SES_REGION=us-east-1
```

#### Slack API Rate Limited

```bash
# Check rate limit headers in logs
kubectl logs deployment/support-portal -n support-portal | grep "X-Rate-Limit-Remaining"

# Mitigation: Batch notifications
kubectl set env deployment/support-portal -n support-portal \
  SLACK_BATCH_NOTIFICATIONS=true \
  SLACK_BATCH_INTERVAL_SECONDS=60
```

#### PagerDuty Integration Key Invalid

```bash
# Rotate integration key
# 1. Go to PagerDuty UI: Services > Support Portal > Integrations
# 2. Generate new Events API v2 integration key
# 3. Update Kubernetes secret
kubectl create secret generic support-portal-pagerduty \
  --from-literal=PAGERDUTY_INTEGRATION_KEY="$NEW_KEY" \
  -n support-portal \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart pods
kubectl rollout restart deployment/support-portal -n support-portal
```

______________________________________________________________________

## Runbook 7: Spam Ticket Attack

### Symptoms

- 1000+ tickets created in < 1 hour
- All from similar email domains
- Subjects contain spam keywords ("viagra", "crypto", etc.)

### Severity: **P3 NORMAL**

### Investigation Steps

```bash
# 1. Identify spam pattern
psql $DATABASE_URL -c "
SELECT
  customer_email,
  COUNT(*) as ticket_count
FROM tickets
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY customer_email
HAVING COUNT(*) > 10
ORDER BY ticket_count DESC;
"

# 2. Check for bot signatures
psql $DATABASE_URL -c "
SELECT DISTINCT user_agent, COUNT(*)
FROM ticket_audit_log
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY user_agent
ORDER BY COUNT(*) DESC;
"
```

### Resolution

```bash
# 1. Block spam email domain
psql $DATABASE_URL -c "
INSERT INTO blocked_email_domains (domain, reason, blocked_at)
VALUES ('spammer.com', 'Spam attack 2026-02-08', NOW());
"

# 2. Delete spam tickets
psql $DATABASE_URL -c "
DELETE FROM tickets
WHERE customer_email LIKE '%@spammer.com'
AND created_at > NOW() - INTERVAL '2 hours';
"

# 3. Enable CAPTCHA on ticket creation form
kubectl set env deployment/support-portal-frontend -n support-portal \
  NEXT_PUBLIC_ENABLE_CAPTCHA=true \
  NEXT_PUBLIC_RECAPTCHA_SITE_KEY="$RECAPTCHA_SITE_KEY"

# 4. Rate limit ticket creation (5 tickets/hour per IP)
kubectl annotate ingress support-portal -n support-portal \
  nginx.ingress.kubernetes.io/rate-limit="5"
```

______________________________________________________________________

## Runbook 8: Database Migration Failure

### Symptoms

- Alembic error during deployment
- Pods in CrashLoopBackOff
- Error: "relation does not exist"

### Severity: **P1 CRITICAL**

### Investigation Steps

```bash
# 1. Check migration history
psql $DATABASE_URL -c "SELECT * FROM alembic_version;"

# 2. Check for failed migration
alembic history
alembic current

# 3. Review migration script
cat libs/python/odg-core/src/odg_core/migrations/versions/<failed_revision>.py
```

### Resolution

#### Option 1: Manual Fix

```bash
# Rollback failed migration
alembic downgrade -1

# Fix migration script (add missing column, etc.)
vim libs/python/odg-core/src/odg_core/migrations/versions/<revision>.py

# Re-run migration
alembic upgrade head

# Verify schema
psql $DATABASE_URL -c "\d+ tickets"
```

#### Option 2: Restore from Backup

```bash
# Stop application
kubectl scale deployment support-portal --replicas=0 -n support-portal

# Restore database
pg_restore -h $DB_HOST -U odg_admin -d support_portal -c backup_pre_migration.dump

# Mark migration as applied (if schema is correct)
psql $DATABASE_URL -c "UPDATE alembic_version SET version_num='<revision>';"

# Restart application
kubectl scale deployment support-portal --replicas=3 -n support-portal
```

______________________________________________________________________

## Runbook 9: TLS Certificate Expiring

### Symptoms

- Alert: "TLS certificate expires in 7 days"
- Browser warning: "Your connection is not secure"

### Severity: **P2 HIGH**

### Investigation Steps

```bash
# Check certificate expiration
echo | openssl s_client -connect support.opendatagov.io:443 2>/dev/null | openssl x509 -noout -dates

# Check cert-manager renewal
kubectl get certificates -n support-portal
kubectl describe certificate support-portal-tls -n support-portal
```

### Resolution

#### Using cert-manager (Automatic)

```bash
# Force renewal
kubectl delete secret support-portal-tls -n support-portal
kubectl delete certificaterequest -n support-portal --all

# Cert-manager will automatically recreate
kubectl get certificate support-portal-tls -n support-portal -w
```

#### Manual Renewal (Let's Encrypt)

```bash
# SSH to control plane
certbot renew --dry-run  # Test first
certbot renew

# Update Kubernetes secret
kubectl create secret tls support-portal-tls \
  --cert=/etc/letsencrypt/live/support.opendatagov.io/fullchain.pem \
  --key=/etc/letsencrypt/live/support.opendatagov.io/privkey.pem \
  -n support-portal \
  --dry-run=client -o yaml | kubectl apply -f -
```

______________________________________________________________________

## Runbook 10: Sudden Traffic Spike / DDoS

### Symptoms

- API response times > 10s
- 1000+ requests/second from single IP
- CloudWatch: network bandwidth saturated

### Severity: **P1 CRITICAL**

### Investigation Steps

```bash
# 1. Check traffic sources
kubectl logs -f deployment/support-portal -n support-portal | awk '{print $1}' | sort | uniq -c | sort -rn | head -20

# 2. Check CloudFront/ALB logs
aws logs tail /aws/cloudfront/support-portal --follow | grep -E "(403|429)"

# 3. Check rate limiting
kubectl logs -f deployment/nginx-ingress-controller -n ingress-nginx | grep "limiting requests"
```

### Resolution

#### Quick Mitigation

```bash
# 1. Block attacking IPs at load balancer
aws wafv2 create-ip-set \
  --name support-portal-blocklist \
  --scope REGIONAL \
  --ip-address-version IPV4 \
  --addresses 1.2.3.4/32 1.2.3.5/32

# 2. Enable aggressive rate limiting
kubectl annotate ingress support-portal -n support-portal \
  nginx.ingress.kubernetes.io/rate-limit="20" \
  nginx.ingress.kubernetes.io/rate-limit-burst="5" \
  --overwrite

# 3. Scale up pods
kubectl scale deployment support-portal --replicas=20 -n support-portal

# 4. Enable CloudFlare DDoS protection (if not already)
# Login to CloudFlare > Security > DDoS > Enable "Attack Mode"
```

#### Long-Term Fix

- [ ] Implement CAPTCHA on high-traffic endpoints
- [ ] Enable AWS Shield Advanced
- [ ] Set up geo-blocking (if attack from specific regions)

______________________________________________________________________

## Emergency Contacts

**On-Call Engineer:** PagerDuty (24/7)
**Database Team:** dba@opendatagov.io
**Security Team:** security@opendatagov.io
**Management:** eng-leadership@opendatagov.io

**External Support:**

- **AWS Premium Support:** 15-minute response
- **Elasticsearch Support:** support@elastic.co
- **SendGrid Support:** https://support.sendgrid.com/

______________________________________________________________________

**Runbook Maintained By:** Engineering Team
**Review Frequency:** Quarterly
**Last Reviewed:** 2026-02-08
