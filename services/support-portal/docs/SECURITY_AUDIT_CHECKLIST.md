# Security Audit Checklist - Support Portal

**Version:** 1.0
**Last Updated:** 2026-02-08
**Status:** Pre-Production Audit

______________________________________________________________________

## Executive Summary

This checklist ensures the Support Portal meets security best practices before production deployment. All items marked ✅ are compliant, ⚠️ need attention, and ❌ are critical issues.

______________________________________________________________________

## 1. Authentication & Authorization

### 1.1 Authentication

- [ ] **JWT tokens** implemented with secure algorithm (RS256 or HS256)
- [ ] Token expiration set (max 1 hour for access tokens)
- [ ] Refresh token rotation implemented
- [ ] Password hashing uses bcrypt/argon2 (min 12 rounds)
- [ ] Multi-factor authentication (MFA) available for staff
- [ ] Session management: logout invalidates tokens
- [ ] Brute-force protection on login endpoints (rate limiting)

### 1.2 Authorization

- [ ] Role-Based Access Control (RBAC) implemented
  - [ ] Customer role: view own tickets only
  - [ ] Agent role: view assigned tickets + queue
  - [ ] Staff role: full access to KB admin
  - [ ] Admin role: system configuration
- [ ] API endpoints check permissions before execution
- [ ] Horizontal privilege escalation prevented (customer A cannot access customer B tickets)
- [ ] Vertical privilege escalation prevented (customer cannot access admin endpoints)

### 1.3 API Security

- [ ] API keys stored in environment variables (not code)
- [ ] API keys rotated regularly (quarterly)
- [ ] Least privilege: each integration has minimal required permissions
- [ ] API rate limiting per user/IP (e.g., 100 req/min)

______________________________________________________________________

## 2. Input Validation & Sanitization

### 2.1 SQL Injection Prevention

- [ ] All database queries use parameterized queries (SQLAlchemy ORM)
- [ ] No raw SQL with string interpolation
- [ ] User input never directly in SQL statements
- [ ] Search queries sanitized (Elasticsearch escaping)

### 2.2 XSS Prevention

- [ ] All user input escaped before rendering HTML
- [ ] Content-Security-Policy (CSP) header configured
- [ ] X-XSS-Protection header enabled
- [ ] Template engine auto-escapes by default
- [ ] Rich text editor (if any) uses allowlist for HTML tags

### 2.3 Injection Attacks

- [ ] Command injection prevented (no shell=True in subprocess)
- [ ] LDAP injection prevented (input escaping)
- [ ] XML injection prevented (defusedxml used)
- [ ] NoSQL injection prevented (MongoDB query sanitization)

### 2.4 Data Validation

- [ ] Email addresses validated (regex + format check)
- [ ] Phone numbers validated
- [ ] File uploads validated:
  - [ ] File type whitelist (no .exe, .sh, .bat)
  - [ ] File size limits (max 10MB)
  - [ ] Magic number verification (not just extension)
  - [ ] Files scanned for malware (ClamAV)
- [ ] Input length limits enforced:
  - [ ] Ticket subject: max 200 chars
  - [ ] Description: max 10,000 chars
  - [ ] Comments: max 5,000 chars

______________________________________________________________________

## 3. Secrets Management

### 3.1 Environment Variables

- [ ] All secrets in `.env` file (not committed to git)
- [ ] `.env.example` template provided (no real secrets)
- [ ] Kubernetes Secrets used in production
- [ ] Secrets Manager integration (AWS Secrets Manager / HashiCorp Vault)

### 3.2 API Keys

- [ ] SendGrid API key: write-only scope
- [ ] Slack bot token: minimal OAuth scopes
- [ ] PagerDuty: integration key (not API key) used for Events API
- [ ] Jira: API token (not password)
- [ ] Elasticsearch: authentication enabled

### 3.3 Database Credentials

- [ ] PostgreSQL password complexity: min 16 chars, alphanumeric + symbols
- [ ] Database user has minimal permissions (no DROP/CREATE DATABASE)
- [ ] Connection strings encrypted in transit (SSL/TLS)

### 3.4 Secret Rotation

- [ ] Secrets rotation policy: every 90 days
- [ ] Automated rotation for cloud provider keys
- [ ] Emergency rotation procedure documented

______________________________________________________________________

## 4. Data Protection

### 4.1 Encryption in Transit

- [ ] HTTPS enforced (redirect HTTP → HTTPS)
- [ ] TLS 1.2+ only (no SSL, TLS 1.0, TLS 1.1)
- [ ] Strong cipher suites configured
- [ ] Certificate from trusted CA (Let's Encrypt / DigiCert)
- [ ] HSTS header configured (max-age=31536000)

### 4.2 Encryption at Rest

- [ ] Database encrypted (PostgreSQL encryption or disk-level)
- [ ] File uploads encrypted (S3 bucket encryption)
- [ ] Backups encrypted
- [ ] Encryption keys stored in KMS (AWS KMS / GCP KMS)

### 4.3 PII Protection

- [ ] Customer email addresses: access logged
- [ ] PII fields: `customer_name`, `customer_email`, `phone_number`
- [ ] Data retention policy: tickets deleted after 7 years
- [ ] GDPR compliance: right to erasure implemented
- [ ] Data anonymization for analytics

### 4.4 Sensitive Data Handling

- [ ] Internal comments: access restricted to staff
- [ ] CSAT feedback: not exposed in public APIs
- [ ] Audit logs: who accessed what ticket when

______________________________________________________________________

## 5. Network Security

### 5.1 Firewall Rules

- [ ] PostgreSQL port (5432): internal network only
- [ ] Elasticsearch port (9200): internal network only
- [ ] Redis port (6379): internal network only
- [ ] Application port (8000): load balancer only
- [ ] SSH port (22): bastion host only

### 5.2 DDoS Protection

- [ ] Cloudflare / AWS Shield enabled
- [ ] Rate limiting at load balancer level
- [ ] SYN flood protection
- [ ] Slowloris protection (connection timeouts)

### 5.3 SSRF Protection

- [ ] Webhook URLs validated (no private IPs)
- [ ] Blocked IP ranges:
  - [ ] 127.0.0.0/8 (localhost)
  - [ ] 10.0.0.0/8 (private)
  - [ ] 172.16.0.0/12 (private)
  - [ ] 192.168.0.0/16 (private)
  - [ ] 169.254.0.0/16 (AWS metadata)
- [ ] DNS rebinding protection

______________________________________________________________________

## 6. Application Security

### 6.1 Dependency Management

- [ ] Dependencies pinned to specific versions (requirements.txt)
- [ ] `safety check` runs in CI/CD (no known vulnerabilities)
- [ ] `pip-audit` runs weekly
- [ ] Automated dependency updates (Dependabot)
- [ ] Security advisories monitored (GitHub Security Alerts)

### 6.2 Code Quality

- [ ] Static analysis: `bandit` for Python security issues
- [ ] Linting: `flake8` / `pylint` for code quality
- [ ] Type checking: `mypy` for type safety
- [ ] Code review: 2 approvals required for main branch

### 6.3 Error Handling

- [ ] Generic error messages to users (no stack traces)
- [ ] Detailed errors logged server-side only
- [ ] Custom error pages (no default framework error pages)
- [ ] Debug mode disabled in production (`DEBUG=False`)

### 6.4 Logging & Monitoring

- [ ] Security events logged:
  - [ ] Failed login attempts
  - [ ] Permission denied (403)
  - [ ] Invalid tokens (401)
  - [ ] Rate limit exceeded (429)
  - [ ] SQL injection attempts
- [ ] Logs sent to centralized logging (CloudWatch / ELK)
- [ ] Log retention: 90 days minimum
- [ ] Sensitive data not logged (passwords, API keys, PII)
- [ ] Alerting configured for security events

______________________________________________________________________

## 7. Infrastructure Security

### 7.1 Container Security

- [ ] Base images from trusted sources (official Docker Hub)
- [ ] Images scanned for vulnerabilities (Trivy / Snyk)
- [ ] Non-root user in containers (`USER appuser`)
- [ ] Read-only filesystem where possible
- [ ] Resource limits configured (CPU, memory)

### 7.2 Kubernetes Security

- [ ] Network policies configured (pod-to-pod traffic restricted)
- [ ] RBAC enabled (service accounts have minimal permissions)
- [ ] Pod Security Standards: Restricted profile
- [ ] Secrets not exposed as environment variables (mounted as volumes)
- [ ] Image pull policy: Always (prevent stale images)

### 7.3 Cloud Security (AWS/GCP/Azure)

- [ ] IAM roles with least privilege
- [ ] VPC configured with private subnets
- [ ] Security groups: whitelist only
- [ ] S3 buckets: private by default (no public read)
- [ ] CloudTrail enabled (audit all API calls)

______________________________________________________________________

## 8. Third-Party Integrations

### 8.1 SendGrid

- [ ] API key: Mail Send permissions only (not Full Access)
- [ ] Verified sender domain (DKIM, SPF, DMARC)
- [ ] Unsubscribe links in emails (CAN-SPAM compliance)

### 8.2 Slack

- [ ] OAuth scopes: `chat:write`, `channels:read` only
- [ ] Bot token stored securely (not user token)
- [ ] Webhook URLs signed (verify requests from Slack)

### 8.3 PagerDuty

- [ ] Integration key used (not API key)
- [ ] Webhooks verified (signature check)
- [ ] Incident deduplication configured

### 8.4 Jira

- [ ] API token (not password)
- [ ] Service account with project-level permissions only
- [ ] Issue webhooks verified (Jira signature)

### 8.5 Webhooks (Outbound)

- [ ] HMAC-SHA256 signatures generated
- [ ] Retry logic: max 3 attempts
- [ ] Timeout: 10 seconds
- [ ] No sensitive data in webhook payloads

______________________________________________________________________

## 9. Compliance

### 9.1 GDPR

- [ ] Privacy policy published
- [ ] Cookie consent banner
- [ ] Right to access: customer can download their data
- [ ] Right to erasure: customer can delete account
- [ ] Data Processing Agreement (DPA) with vendors
- [ ] Data breach notification procedure (< 72 hours)

### 9.2 SOC 2

- [ ] Access controls documented
- [ ] Change management process
- [ ] Incident response plan
- [ ] Vendor risk assessments

### 9.3 HIPAA (if handling health data)

- [ ] Business Associate Agreement (BAA)
- [ ] Audit logs for PHI access
- [ ] Data encryption (in transit + at rest)

______________________________________________________________________

## 10. Incident Response

### 10.1 Incident Response Plan

- [ ] Security incident runbook created
- [ ] Escalation path documented
- [ ] Communication plan (internal + customer)
- [ ] Post-mortem template

### 10.2 Backup & Recovery

- [ ] Database backups: daily (automated)
- [ ] Backup retention: 30 days
- [ ] Backup restoration tested (quarterly)
- [ ] RTO (Recovery Time Objective): < 4 hours
- [ ] RPO (Recovery Point Objective): < 1 hour

### 10.3 Disaster Recovery

- [ ] Multi-region failover configured
- [ ] Disaster recovery drills: annually
- [ ] Critical system dependencies documented

______________________________________________________________________

## 11. Testing

### 11.1 Security Testing

- [ ] SAST (Static Application Security Testing): Bandit, SonarQube
- [ ] DAST (Dynamic Application Security Testing): OWASP ZAP
- [ ] Dependency scanning: Safety, pip-audit
- [ ] Penetration testing: external vendor (annually)

### 11.2 Vulnerability Scanning

- [ ] Container image scanning: Trivy
- [ ] Infrastructure scanning: AWS Inspector
- [ ] Quarterly vulnerability assessments

### 11.3 Bug Bounty Program

- [ ] Public bug bounty program (HackerOne / Bugcrowd)
- [ ] Scope defined (in-scope domains, out-of-scope)
- [ ] Rewards: $100 - $5,000 based on severity

______________________________________________________________________

## 12. Documentation

### 12.1 Security Documentation

- [ ] Security architecture diagram
- [ ] Threat model documented
- [ ] Security policies published (internal wiki)
- [ ] Runbooks for common security incidents

### 12.2 Training

- [ ] Security awareness training for all staff (annual)
- [ ] Secure coding training for engineers (quarterly)
- [ ] Phishing simulation tests (quarterly)

______________________________________________________________________

## Action Items

### Critical (Must Fix Before Production)

1. ❌ Implement JWT authentication for API endpoints
1. ❌ Enable HTTPS with valid TLS certificate
1. ❌ Configure rate limiting (100 req/min per IP)
1. ❌ Add input validation for all user-provided fields
1. ❌ Store secrets in Kubernetes Secrets (not .env in image)

### High Priority (Fix Within 2 Weeks)

6. ⚠️ Enable database encryption at rest
1. ⚠️ Configure Content-Security-Policy header
1. ⚠️ Add webhook signature verification
1. ⚠️ Implement audit logging for security events
1. ⚠️ Run penetration test with external vendor

### Medium Priority (Fix Within 1 Month)

11. ⚠️ Set up automated dependency scanning in CI/CD
01. ⚠️ Create incident response runbook
01. ⚠️ Configure Kubernetes network policies
01. ⚠️ Add GDPR data export functionality

### Low Priority (Nice to Have)

15. Configure DDoS protection (Cloudflare)
01. Set up bug bounty program
01. Quarterly security awareness training

______________________________________________________________________

## Sign-Off

**Security Review Completed By:** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
**Date:** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
**Approved for Production:** ☐ Yes ☐ No ☐ Conditional

**Conditions for Approval:**

______________________________________________________________________

______________________________________________________________________

______________________________________________________________________
