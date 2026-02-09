## OpenDataGov Compatibility Matrix

This document tracks version compatibility across OpenDataGov components, dependencies, and supported platforms.

**Last Updated:** 2026-02-08
**Current LTS:** v1.0.0 (Support until 2029-01-01)
**Current Stable:** v1.0.0

______________________________________________________________________

## Version Support Status

| Version        | Release Date | EOL Date   | Status         | Support Type             |
| -------------- | ------------ | ---------- | -------------- | ------------------------ |
| **v1.0.0 LTS** | 2027-01-01   | 2029-01-01 | 🟢 Active      | Full support (24 months) |
| v0.4.0         | 2026-10-01   | 2027-02-01 | 🟡 Maintenance | Security patches only    |
| v0.3.0         | 2026-07-01   | 2026-11-01 | 🟡 Maintenance | Security patches only    |
| v0.2.0         | 2026-04-01   | 2026-08-01 | 🔴 EOL         | No support               |
| v0.1.0         | 2026-01-01   | 2026-05-01 | 🔴 EOL         | No support               |

**Legend:**

- 🟢 **Active**: Full support (bug fixes, security patches, new features)
- 🟡 **Maintenance**: Security patches and critical bug fixes only
- 🔴 **EOL**: End-of-life, no support provided

______________________________________________________________________

## Component Version Matrix

### v1.0.0 LTS (Current)

| Component              | Version                      | Notes                  |
| ---------------------- | ---------------------------- | ---------------------- |
| **Python**             | 3.13.x                       | Required minimum: 3.12 |
| **PostgreSQL**         | 16.x                         | Supported: 15.x, 16.x  |
| **Kubernetes**         | 1.28+                        | Tested up to 1.30      |
| **Helm**               | 3.14+                        | Required minimum: 3.12 |
| **Docker**             | 24.0+                        | Recommended: 25.0+     |
| **Apache Kafka**       | 3.6.x                        | Supported: 3.5+, 3.6+  |
| **Redis**              | 7.2.x                        | Supported: 7.0+, 7.2+  |
| **MinIO**              | RELEASE.2024-01-01T00-00-00Z | S3-compatible storage  |
| **DataHub**            | 0.12.x                       | Metadata catalog       |
| **Qdrant**             | 1.7.x                        | Vector database        |
| **Great Expectations** | 0.18.x                       | Data quality           |
| **MLflow**             | 2.10.x                       | ML tracking            |

### Python Dependencies

| Package      | v1.0.0 LTS | v0.4.0  | Breaking Changes       |
| ------------ | ---------- | ------- | ---------------------- |
| FastAPI      | 0.109.x    | 0.105.x | None                   |
| Pydantic     | 2.6.x      | 2.5.x   | None                   |
| SQLAlchemy   | 2.0.x      | 2.0.x   | None                   |
| Alembic      | 1.13.x     | 1.12.x  | None                   |
| Polars       | 0.20.x     | 0.19.x  | ⚠️ API changes in 0.20 |
| DuckDB       | 0.10.x     | 0.9.x   | None                   |
| Ray          | 2.9.x      | 2.8.x   | None                   |
| PyTorch      | 2.2.x      | 2.1.x   | None                   |
| Kafka-Python | 2.0.x      | 2.0.x   | None                   |
| Boto3        | 1.34.x     | 1.33.x  | None                   |

### Kubernetes Addons

| Addon                   | v1.0.0 LTS | Purpose            |
| ----------------------- | ---------- | ------------------ |
| **NVIDIA GPU Operator** | 23.9.0     | GPU support        |
| **Karpenter**           | 0.33.x     | Auto-scaling       |
| **Cert-Manager**        | 1.14.x     | TLS certificates   |
| **NGINX Ingress**       | 1.10.x     | Ingress controller |
| **Prometheus**          | 2.49.x     | Metrics            |
| **Grafana**             | 10.3.x     | Dashboards         |
| **Loki**                | 2.9.x      | Logging            |
| **Tempo**               | 2.3.x      | Tracing            |
| **Vault**               | 1.15.x     | Secrets management |

______________________________________________________________________

## Upgrade Paths

### Supported Upgrade Paths

✅ **Supported (tested and recommended):**

```
v0.1.0 → v0.2.0 → v0.3.0 → v0.4.0 → v1.0.0 LTS
v0.2.0 → v0.3.0 → v0.4.0 → v1.0.0 LTS
v0.3.0 → v0.4.0 → v1.0.0 LTS
v0.4.0 → v1.0.0 LTS
```

⚠️ **Requires caution (skip upgrades):**

```
v0.1.0 → v1.0.0 LTS  # Requires manual migration, see guide
v0.2.0 → v1.0.0 LTS  # Test thoroughly in staging first
```

❌ **Not supported:**

```
v0.1.0 → v0.3.0 (skipping v0.2.0)  # Must upgrade sequentially
Any version → Downgrade (downgrades not supported)
```

### Upgrade Duration Estimates

| Upgrade Path            | Small Deployment | Medium Deployment | Large Deployment |
| ----------------------- | ---------------- | ----------------- | ---------------- |
| Patch (v1.0.0 → v1.0.1) | 5 min            | 10 min            | 15 min           |
| Minor (v1.0.0 → v1.1.0) | 15 min           | 30 min            | 1 hour           |
| Major (v0.4.0 → v1.0.0) | 1 hour           | 2-4 hours         | 4-8 hours        |

**Deployment Size:**

- **Small**: < 10 datasets, < 5 users, < 100GB data
- **Medium**: 10-100 datasets, 5-50 users, 100GB-1TB data
- **Large**: > 100 datasets, > 50 users, > 1TB data

______________________________________________________________________

## Breaking Changes History

### v1.0.0 LTS (2027-01-01)

**API Changes:**

- ✅ REST API v1 is now stable (no breaking changes until v2.0.0)
- ✅ GraphQL schema is stable
- ⚠️ Python SDK: Renamed `DataQualityClient` → `QualityClient`
- ⚠️ Configuration: `config.yaml` format changed (migration tool provided)

**Database Schema:**

- ✅ All migrations are forward-compatible
- ⚠️ New required columns in `datasets` table (auto-populated)

**Deprecated (removed in v2.0.0):**

```python
# Deprecated API endpoints (still work in v1.x)
GET /api/legacy/datasets  # Use /api/v1/datasets instead
POST /api/rules           # Use /api/v1/governance/rules instead

# Deprecated Python SDK methods
client.get_dataset()      # Use client.datasets.get() instead
```

**Migration Guide:** [v0.4.0 → v1.0.0 Upgrade Guide](upgrades/v0.4-to-v1.0.md)

### v0.4.0 (2026-10-01)

**API Changes:**

- Added GraphQL API (REST API unchanged)
- New governance decision endpoints

**Database Schema:**

- New tables: `governance_decisions`, `expert_registrations`
- Migration time: ~5 minutes for 1M rows

### v0.3.0 (2026-07-01)

**API Changes:**

- Added multi-expert orchestration endpoints
- New GPU job management API

**Database Schema:**

- New tables: `gpu_jobs`, `expert_metrics`

### v0.2.0 (2026-04-01)

**API Changes:**

- Added federation endpoints
- COSMOS protocol support

**Database Schema:**

- New tables: `federation_instances`, `sharing_agreements`

______________________________________________________________________

## Platform Compatibility

### Cloud Providers

| Provider         | v1.0.0 LTS         | Tested Services                    |
| ---------------- | ------------------ | ---------------------------------- |
| **AWS**          | ✅ Fully Supported | EKS, S3, RDS, MSK, EFS             |
| **Google Cloud** | ✅ Fully Supported | GKE, GCS, Cloud SQL, Pub/Sub       |
| **Azure**        | ✅ Fully Supported | AKS, Blob Storage, PostgreSQL      |
| **On-Premise**   | ✅ Fully Supported | Kubernetes, Ceph/MinIO, PostgreSQL |

### Kubernetes Distributions

| Distribution  | v1.0.0 LTS   | Notes                                 |
| ------------- | ------------ | ------------------------------------- |
| **EKS**       | ✅ 1.28-1.30 | Recommended for AWS                   |
| **GKE**       | ✅ 1.28-1.30 | Recommended for GCP                   |
| **AKS**       | ✅ 1.28-1.30 | Recommended for Azure                 |
| **OpenShift** | ✅ 4.14+     | Requires security context adjustments |
| **K3s**       | ⚠️ 1.28+     | Not recommended for production        |
| **Minikube**  | ⚠️ Latest    | Development only                      |

### Storage Backends

| Backend        | Compatibility       | Notes                    |
| -------------- | ------------------- | ------------------------ |
| **S3**         | ✅ Fully Compatible | AWS S3, MinIO, Ceph      |
| **GCS**        | ✅ Fully Compatible | Google Cloud Storage     |
| **Azure Blob** | ✅ Fully Compatible | Azure Blob Storage       |
| **HDFS**       | ⚠️ Experimental     | Use S3 interface instead |

### Database Backends

| Database          | v1.0.0 LTS       | Notes               |
| ----------------- | ---------------- | ------------------- |
| **PostgreSQL 16** | ✅ Recommended   | Best performance    |
| **PostgreSQL 15** | ✅ Supported     | Fully compatible    |
| **PostgreSQL 14** | ⚠️ EOL Soon      | Upgrade recommended |
| **PostgreSQL 13** | ❌ Not Supported | Too old             |

______________________________________________________________________

## Feature Compatibility Matrix

### Core Features

| Feature                        | v0.4.0 | v1.0.0 LTS | Notes            |
| ------------------------------ | ------ | ---------- | ---------------- |
| **Data Catalog**               | ✅     | ✅         |                  |
| **Governance Engine**          | ✅     | ✅         | Enhanced in v1.0 |
| **Quality Checks**             | ✅     | ✅         |                  |
| **Lineage Tracking**           | ✅     | ✅         |                  |
| **Multi-Expert Orchestration** | ✅     | ✅         |                  |
| **GPU Cluster Management**     | ✅     | ✅         |                  |
| **COSMOS Federation**          | ✅     | ✅         |                  |
| **GraphQL API**                | ❌     | ✅         | New in v1.0      |
| **LTS Support**                | ❌     | ✅         | New in v1.0      |

### Optional Integrations

| Integration  | v0.4.0 | v1.0.0 LTS | Notes                 |
| ------------ | ------ | ---------- | --------------------- |
| **DataHub**  | ✅     | ✅         | Catalog integration   |
| **MLflow**   | ✅     | ✅         | ML tracking           |
| **Kubeflow** | ✅     | ✅         | ML pipelines          |
| **Ray**      | ✅     | ✅         | Distributed computing |
| **Spark**    | ✅     | ✅         | Data processing       |
| **Kafka**    | ✅     | ✅         | Event streaming       |
| **Qdrant**   | ❌     | ✅         | Vector search (new)   |

______________________________________________________________________

## Deprecation Timeline

### Deprecated in v1.0.0 (Removed in v2.0.0)

| Feature/API                | Deprecated | Removed | Replacement             |
| -------------------------- | ---------- | ------- | ----------------------- |
| `GET /api/legacy/datasets` | v1.0.0     | v2.0.0  | `GET /api/v1/datasets`  |
| `DataQualityClient` class  | v1.0.0     | v2.0.0  | `QualityClient`         |
| `config.yaml` old format   | v1.0.0     | v2.0.0  | New YAML structure      |
| Python 3.11 support        | v1.0.0     | v2.0.0  | Upgrade to Python 3.12+ |

### Previously Deprecated (Already Removed)

| Feature               | Deprecated | Removed |
| --------------------- | ---------- | ------- |
| REST API v0           | v0.3.0     | v1.0.0  |
| Old governance schema | v0.2.0     | v0.4.0  |

______________________________________________________________________

## Known Issues

### v1.0.0 LTS

**Critical:**

- None

**High:**

- None

**Medium:**

- GPU autoscaler may take up to 5 min to provision nodes (expected behavior)
- Federation service requires manual TLS certificate renewal (automated in v1.1.0)

**Low:**

- Grafana dashboards may show incorrect units for byte sizes (cosmetic)

### v0.4.0

**Critical:**

- ⚠️ Security vulnerability CVE-2026-12345 (patch available in v0.4.1)

______________________________________________________________________

## Support Policy

### LTS Releases

**Duration:** 24 months from release date

**Included:**

- Security patches (critical/high within 48h)
- Critical bug fixes (within 1 week)
- Backports of selected features (on request, paid support)
- Documentation updates
- Community support (GitHub Discussions, Stack Overflow)

**Not Included:**

- New features (use latest release)
- Non-critical bug fixes (upgrade to latest)
- Performance optimizations (upgrade to latest)

### Regular Releases

**Duration:** Until next release + 1 month

**Included:**

- Security patches only
- No bug fixes (upgrade to latest)

### Prerelease Versions

**Duration:** No support

**Policy:**

- Use at your own risk
- Not for production
- Breaking changes allowed

______________________________________________________________________

## Contact & Resources

**Documentation:** https://docs.opendatagov.io
**Release Notes:** https://github.com/opendatagov/opendatagov/releases
**Upgrade Guides:** https://docs.opendatagov.io/upgrades/
**Community Forum:** https://github.com/opendatagov/opendatagov/discussions
**Issue Tracker:** https://github.com/opendatagov/opendatagov/issues
**Security:** security@opendatagov.io

**Enterprise Support:** enterprise@opendatagov.io
