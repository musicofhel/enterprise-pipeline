# Data Security and Privacy Policy

**Document Version:** 4.1
**Effective Date:** December 1, 2025
**Owner:** Information Security Team
**Last Reviewed:** November 20, 2025
**Classification:** Internal - Sensitive

---

## 1. Overview

Meridian AI Systems is committed to protecting the confidentiality, integrity, and availability of all data entrusted to us by our customers, partners, and employees. This policy defines the technical and organizational measures we implement to safeguard data across our platform and operations.

Meridian AI Systems maintains **SOC 2 Type II** certification (most recent audit completed September 2025) and complies with GDPR, CCPA, and HIPAA where applicable.

## 2. Data Classification

All data handled by Meridian AI Systems is classified into four tiers:

| Classification | Description | Examples | Access |
|---|---|---|---|
| **Public** | Information intended for public consumption | Marketing content, public docs | All employees |
| **Internal** | Business information not intended for public release | Internal wikis, roadmaps | All employees |
| **Confidential** | Sensitive business or customer data | Customer PII, financial data | Role-based access |
| **Restricted** | Highly sensitive data requiring maximum protection | Encryption keys, credentials, PHI | Named individuals only |

All data defaults to **Confidential** classification unless explicitly marked otherwise.

## 3. Encryption Standards

### Data at Rest
- All customer data is encrypted using **AES-256** encryption
- Database volumes use **AWS EBS encryption** with customer-managed KMS keys
- S3 buckets use **SSE-KMS** (Server-Side Encryption with AWS Key Management Service)
- Backup archives are encrypted with AES-256-GCM before transfer to cold storage

### Data in Transit
- All API communications use **TLS 1.3** (minimum TLS 1.2 for legacy client compatibility)
- Internal service-to-service communication uses **mTLS** (mutual TLS) via Istio service mesh
- WebSocket connections for real-time features use **WSS** (WebSocket Secure)
- TLS certificates are issued by AWS Certificate Manager and auto-renewed 30 days before expiry

### Key Management
- Encryption keys are managed through **AWS Key Management Service (KMS)**
- Automatic key rotation occurs every **365 days**
- Key access is restricted via IAM policies with least-privilege principles
- Key usage is logged in AWS CloudTrail and reviewed monthly by the Security team
- Emergency key revocation can be initiated by any member of the Security team with approval from the CISO

## 4. Data Retention

| Data Type | Retention Period | Storage Location | Deletion Method |
|---|---|---|---|
| Customer data (active) | Duration of contract + 90 days | Primary RDS (us-east-1) | Automated purge job |
| Customer data (archived) | **7 years** from contract end | S3 Glacier Deep Archive | Lifecycle policy |
| Audit logs | **10 years** | CloudWatch Logs + S3 | Lifecycle policy |
| Application logs | 90 days | CloudWatch Logs | Auto-expiry |
| Session data | 24 hours | Redis cluster | TTL-based eviction |
| Employee HR records | 7 years post-termination | PeopleHub (encrypted) | Manual with Legal approval |
| Marketing analytics | 2 years | BigQuery | Automated purge |

## 5. GDPR Compliance

Meridian AI Systems complies with the EU General Data Protection Regulation (GDPR) for all EU/EEA customer data:

### Right to Erasure (Article 17)
- Deletion requests must be fulfilled within **72 hours** of verified request receipt
- Deletion is propagated across all systems including backups within **30 days**
- A deletion confirmation receipt is sent to the data subject via email
- Deletion requests are logged in the Data Subject Request (DSR) tracker with a unique reference ID

### Data Processing
- All EU customer data is processed and stored within the **eu-west-1 (Ireland)** AWS region
- A Data Processing Agreement (DPA) is available for all customers upon request
- Sub-processor list is maintained at https://meridian-ai.com/legal/sub-processors and updated with 30 days' notice before adding new sub-processors
- Data Protection Impact Assessments (DPIAs) are conducted for any new processing activity involving personal data

### Lawful Basis
- Customer data processing: **Contractual necessity** (Article 6(1)(b))
- Marketing communications: **Consent** (Article 6(1)(a)), with opt-out in every communication
- Security logging: **Legitimate interest** (Article 6(1)(f))

## 6. Backup and Disaster Recovery

### Database Backups
- **PostgreSQL** production databases are backed up every **6 hours** using automated RDS snapshots
- Backup retention: **30 days** for daily snapshots, **1 year** for monthly snapshots
- Cross-region replication to **us-west-2 (Oregon)** for disaster recovery
- Recovery Point Objective (RPO): **6 hours**
- Recovery Time Objective (RTO): **4 hours** for P1 incidents, **24 hours** for non-critical recovery

### Backup Testing
- Full restore tests are conducted **quarterly** using production backup snapshots
- Results are documented in the Disaster Recovery Runbook and reviewed by the SRE team
- Last successful restore test: **October 15, 2025** (restore completed in 2 hours 14 minutes)

### Business Continuity
- Multi-AZ deployment across **3 availability zones** in each active region
- Automatic failover for RDS, ElastiCache, and application load balancers
- DR site in us-west-2 can be promoted to primary within 4 hours
- Annual tabletop DR exercise conducted with engineering and operations leadership

## 7. Secrets Management

- All application secrets are stored in **AWS Secrets Manager**
- Secret rotation occurs every **90 days** (automated for database credentials, API keys, and service tokens)
- Application code **never** hardcodes secrets; all secrets are injected via environment variables at runtime through ECS task definitions
- IAM roles are used for service-to-service authentication instead of long-lived credentials wherever possible
- Secret access is logged and auditable via CloudTrail
- Developer workstation secrets use **1Password Teams** with mandatory master password + hardware key (YubiKey)

## 8. Access Control

### Authentication
- All internal systems require **SSO** via Okta with **MFA** (hardware token or authenticator app)
- Service accounts use **IAM roles** with scoped permissions, never shared credentials
- API access uses **short-lived tokens** (1-hour expiry) issued via OAuth 2.0

### Authorization
- Role-Based Access Control (**RBAC**) is enforced across all systems
- Production database access requires **break-glass approval** via PagerDuty with automatic 4-hour session expiry
- Quarterly access reviews are conducted by each team lead; stale accounts are deprovisioned within 5 business days
- Offboarding checklist includes revocation of all system access within **2 hours** of termination notification

## 9. Vulnerability Management

- Automated dependency scanning via **Snyk** on every pull request
- Container image scanning with **Trivy** before deployment to production
- Penetration testing conducted **annually** by an independent third party (NCC Group; last engagement: August 2025)
- Critical vulnerabilities (CVSS 9.0+) must be patched within **72 hours**
- High vulnerabilities (CVSS 7.0-8.9) must be patched within **14 days**
- Bug bounty program available at https://meridian-ai.com/security/bug-bounty

## 10. Incident Reporting

All security incidents must be reported immediately to the Security team via:
- **Slack:** #security-incidents (for non-sensitive initial reports)
- **Email:** security@meridian-ai.com (for sensitive details)
- **PagerDuty:** Security On-Call escalation (for active breaches)

Employees who report security concerns in good faith are protected under the company's Whistleblower Policy.

---

*This policy is reviewed semi-annually. Next scheduled review: June 2026.*
