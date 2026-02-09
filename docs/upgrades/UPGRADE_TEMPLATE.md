# Upgrade Guide: vX.Y.Z → vA.B.C

**Release Date:** YYYY-MM-DD
**Upgrade Duration:** ~X hours (medium deployment)
**Difficulty:** 🟢 Easy / 🟡 Medium / 🔴 Hard

______________________________________________________________________

## Overview

**What's New:**

- Summary of major changes
- New features introduced
- Performance improvements
- Security enhancements

**Breaking Changes:**

- List of breaking changes
- Impact on existing deployments
- Required actions

**Deprecated:**

- Features/APIs deprecated in this version
- Timeline for removal
- Migration path

______________________________________________________________________

## Prerequisites

### Version Requirements

**Current Version:**

- Minimum: vX.Y.Z
- Recommended: Latest patch of vX.Y

**Target Version:**

- Version: vA.B.C
- Type: Patch / Minor / Major / LTS

### Compatibility Check

| Component  | Minimum Version | Recommended |
| ---------- | --------------- | ----------- |
| Kubernetes | 1.XX+           | 1.YY+       |
| Helm       | 3.XX+           | 3.YY+       |
| PostgreSQL | 1X              | 1Y          |
| Python     | 3.XX            | 3.YY        |

### Pre-Upgrade Checklist

- [ ] Backup database (mandatory)
- [ ] Backup current Helm values
- [ ] Test upgrade in staging environment
- [ ] Review breaking changes
- [ ] Schedule maintenance window
- [ ] Notify users of upgrade
- [ ] Prepare rollback plan

______________________________________________________________________

## Backup Procedure

### 1. Database Backup

```bash
# PostgreSQL backup
kubectl exec -it postgresql-0 -- \
  pg_dumpall -U postgres > backup_$(date +%Y%m%d_%H%M%S).sql

# Verify backup
ls -lh backup_*.sql
```

### 2. Configuration Backup

```bash
# Export current Helm values
helm get values opendatagov -n opendatagov > values_backup.yaml

# Export all ConfigMaps and Secrets
kubectl get configmaps -n opendatagov -o yaml > configmaps_backup.yaml
kubectl get secrets -n opendatagov -o yaml > secrets_backup.yaml
```

### 3. Persistent Volume Snapshot (if available)

```bash
# AWS EBS snapshot
aws ec2 create-snapshot \
  --volume-id vol-xxx \
  --description "Pre-upgrade backup vX.Y.Z"

# GCP Persistent Disk snapshot
gcloud compute disks snapshot DISK_NAME \
  --snapshot-names=pre-upgrade-vxyz
```

______________________________________________________________________

## Upgrade Steps

### Step 1: Prepare Environment

```bash
# Set version variables
OLD_VERSION="vX.Y.Z"
NEW_VERSION="vA.B.C"

# Verify current version
helm list -n opendatagov

# Fetch new Helm chart
helm repo update
helm search repo opendatagov --versions | head -n 5
```

### Step 2: Review Changes

```bash
# Download new values file
helm show values oci://ghcr.io/opendatagov/opendatagov --version ${NEW_VERSION} > values_new.yaml

# Compare with current values
diff values_backup.yaml values_new.yaml
```

### Step 3: Database Migrations

**Test migrations (dry-run):**

```bash
# Run migration check
kubectl exec -it governance-engine-0 -- \
  python -m alembic upgrade head --sql > migration_${NEW_VERSION}.sql

# Review SQL
cat migration_${NEW_VERSION}.sql
```

**Apply migrations:**

```bash
# Option 1: Automatic (recommended)
kubectl exec -it governance-engine-0 -- \
  python -m alembic upgrade head

# Option 2: Manual (for critical upgrades)
kubectl exec -it postgresql-0 -- \
  psql -U postgres -d governance < migration_${NEW_VERSION}.sql
```

### Step 4: Update Helm Chart

**Rolling Update (zero-downtime):**

```bash
helm upgrade opendatagov \
  oci://ghcr.io/opendatagov/opendatagov \
  --version ${NEW_VERSION} \
  --namespace opendatagov \
  --reuse-values \
  --wait \
  --timeout 30m
```

**Blue/Green Deployment (recommended for major upgrades):**

```bash
# Deploy new version in separate namespace
helm install opendatagov-${NEW_VERSION} \
  oci://ghcr.io/opendatagov/opendatagov \
  --version ${NEW_VERSION} \
  --namespace opendatagov-green \
  --create-namespace \
  --values values_backup.yaml

# Test green environment
kubectl port-forward -n opendatagov-green svc/governance-engine 8080:8000
curl http://localhost:8080/health

# Switch traffic (update Ingress)
kubectl patch ingress opendatagov -n opendatagov \
  --type='json' \
  -p='[{"op": "replace", "path": "/spec/rules/0/http/paths/0/backend/service/name", "value": "governance-engine-green"}]'

# Monitor for 30 minutes, then delete old version
helm uninstall opendatagov -n opendatagov
```

### Step 5: Verify Upgrade

```bash
# Check pod status
kubectl get pods -n opendatagov

# Verify version
kubectl exec -it governance-engine-0 -- cat /app/VERSION

# Run health checks
kubectl exec -it governance-engine-0 -- \
  python -m pytest tests/health_check.py

# Check logs for errors
kubectl logs -n opendatagov deployment/governance-engine --tail=100
```

### Step 6: Smoke Tests

```bash
# Test critical endpoints
curl https://opendatagov.io/health
curl https://opendatagov.io/api/v1/datasets

# Test GraphQL API
curl -X POST https://opendatagov.io/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ datasets { id name } }"}'

# Test job submission
python scripts/smoke_test.py
```

______________________________________________________________________

## Breaking Changes & Migration

### Breaking Change 1: [Description]

**Impact:**

- What breaks
- Which users are affected

**Migration:**

```bash
# Before
old_command --old-flag

# After
new_command --new-flag
```

**Code Changes:**

```python
# Before (deprecated)
from odg_core import OldClass
client = OldClass()

# After (required)
from odg_core import NewClass
client = NewClass()
```

### Breaking Change 2: [Description]

[Same structure as above]

______________________________________________________________________

## Configuration Changes

### New Configuration Options

```yaml
# New values to add to values.yaml
newFeature:
  enabled: true
  replicas: 2
  timeout: 300
```

### Deprecated Configuration

```yaml
# Remove these from values.yaml (no longer supported)
oldFeature:
  enabled: false  # REMOVE THIS
```

### Modified Defaults

| Setting    | Old Default | New Default | Notes            |
| ---------- | ----------- | ----------- | ---------------- |
| `replicas` | 1           | 2           | Increased for HA |
| `timeout`  | 30s         | 60s         | Longer timeout   |

______________________________________________________________________

## Rollback Procedure

If upgrade fails, follow these steps:

### 1. Helm Rollback

```bash
# Rollback to previous release
helm rollback opendatagov -n opendatagov

# Verify rollback
helm history opendatagov -n opendatagov
```

### 2. Database Rollback

```bash
# Rollback migrations (if supported)
kubectl exec -it governance-engine-0 -- \
  python -m alembic downgrade -1

# Or restore from backup
kubectl exec -i postgresql-0 -- \
  psql -U postgres < backup_YYYYMMDD_HHMMSS.sql
```

### 3. Verify Rollback

```bash
# Check version
kubectl exec -it governance-engine-0 -- cat /app/VERSION

# Run health checks
curl https://opendatagov.io/health
```

______________________________________________________________________

## Troubleshooting

### Issue: Database Migration Fails

**Symptoms:**

```
Error: column "new_field" already exists
```

**Solution:**

```bash
# Check migration status
kubectl exec -it governance-engine-0 -- \
  python -m alembic current

# Manually fix migration
kubectl exec -it postgresql-0 -- \
  psql -U postgres -d governance -c "DROP COLUMN new_field;"

# Retry migration
kubectl exec -it governance-engine-0 -- \
  python -m alembic upgrade head
```

### Issue: Pods CrashLoopBackOff

**Symptoms:**

```
governance-engine-0   0/1     CrashLoopBackOff
```

**Solution:**

```bash
# Check logs
kubectl logs -n opendatagov governance-engine-0

# Check events
kubectl describe pod -n opendatagov governance-engine-0

# Common fix: Restart pods
kubectl rollout restart deployment/governance-engine -n opendatagov
```

### Issue: Configuration Error

**Symptoms:**

```
Error: validation error in values.yaml
```

**Solution:**

```bash
# Validate values file
helm template opendatagov \
  oci://ghcr.io/opendatagov/opendatagov \
  --version ${NEW_VERSION} \
  --values values_backup.yaml \
  --debug

# Fix errors and retry
helm upgrade opendatagov ...
```

______________________________________________________________________

## Post-Upgrade Tasks

### 1. Update Client SDKs

```bash
# Update Python SDK
pip install --upgrade odg-core==${NEW_VERSION}

# Update CLI
pip install --upgrade odg-cli==${NEW_VERSION}
```

### 2. Update Documentation

- [ ] Update internal runbooks
- [ ] Notify team of new features
- [ ] Update API documentation
- [ ] Update Grafana dashboards (if needed)

### 3. Monitor Performance

```bash
# Check Prometheus metrics
kubectl port-forward -n monitoring svc/prometheus 9090:9090

# Open Grafana
kubectl port-forward -n monitoring svc/grafana 3000:80

# Monitor for 24-48 hours after upgrade
```

### 4. Cleanup

```bash
# Remove old Docker images (optional)
docker system prune -a

# Remove old PVCs (if using blue/green)
kubectl delete pvc -n opendatagov-green --all
```

______________________________________________________________________

## Support & Resources

**Documentation:** https://docs.opendatagov.io/upgrades/${NEW_VERSION}
**Release Notes:** https://github.com/opendatagov/opendatagov/releases/tag/${NEW_VERSION}
**Community Forum:** https://github.com/opendatagov/opendatagov/discussions
**Issue Tracker:** https://github.com/opendatagov/opendatagov/issues

**Need Help?**

- Community Support: https://github.com/opendatagov/opendatagov/discussions
- Enterprise Support: enterprise@opendatagov.io
- Security Issues: security@opendatagov.io

______________________________________________________________________

## Appendix

### A. Full values.yaml Diff

```yaml
# Detailed diff of all changes
# (auto-generated)
```

### B. Migration SQL Script

```sql
-- Full migration SQL
-- (auto-generated by Alembic)
```

### C. Deprecated APIs

| Endpoint       | Deprecated | Removed | Replacement       |
| -------------- | ---------- | ------- | ----------------- |
| `GET /api/old` | vX.Y.Z     | vA.B.C  | `GET /api/v1/new` |
