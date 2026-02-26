# Incident Response Plan

**Document Version:** 3.4
**Effective Date:** February 1, 2026
**Owner:** Site Reliability Engineering (SRE)
**Last Reviewed:** January 28, 2026
**Classification:** Internal

---

## 1. Purpose

This document defines Meridian AI Systems' incident response procedures for production service disruptions, security events, and data integrity issues. All engineering, SRE, and operations personnel must be familiar with these procedures.

## 2. Severity Levels

### P1 - Critical

**Definition:** Complete service outage, data breach, or security incident affecting all customers.

| Attribute | Requirement |
|---|---|
| **Detection** | Automated alerting via Datadog + PagerDuty |
| **Response** | Auto-page on-call SRE immediately |
| **War room** | Opened within **10 minutes** of detection |
| **Response SLA** | **15 minutes** from page to first responder acknowledgment |
| **Resolution target** | 4 hours |
| **Communication** | Status page updated within 15 minutes; customer email within 30 minutes |
| **Escalation** | VP of Engineering notified within 30 minutes; CTO within 1 hour |
| **Post-mortem** | Required within **48 hours** |

**Examples:** API returning 5xx for all requests, database corruption, unauthorized data access, complete loss of a production region.

### P2 - High

**Definition:** Significant degradation affecting a subset of customers or a major feature.

| Attribute | Requirement |
|---|---|
| **Detection** | Automated alerting or customer report |
| **Response SLA** | **1 hour** from detection |
| **Resolution target** | Same business day |
| **Communication** | Status page updated within 1 hour |
| **Escalation** | Engineering Manager notified within 2 hours |
| **Post-mortem** | Required within 5 business days |

**Examples:** Query latency exceeding 10 seconds (p95), ingestion pipeline stalled, single availability zone failure, elevated error rates (>5%) on a core endpoint.

### P3 - Medium

**Definition:** Minor degradation with limited customer impact or a non-critical system issue.

| Attribute | Requirement |
|---|---|
| **Detection** | Monitoring alert, internal report, or customer ticket |
| **Response SLA** | **4 hours** during business hours |
| **Resolution target** | Next business day |
| **Communication** | Internal Slack update; status page only if customer-facing |
| **Escalation** | Team lead notified |
| **Post-mortem** | Optional; recommended if recurring |

**Examples:** Dashboard loading slowly, webhook delivery delays, non-critical background job failures, staging environment issues.

### P4 - Low

**Definition:** Cosmetic issues, minor bugs, or internal tooling problems with no customer impact.

| Attribute | Requirement |
|---|---|
| **Response SLA** | Next sprint planning |
| **Resolution target** | Within current sprint |
| **Post-mortem** | Not required |

**Examples:** Typo in error message, internal dashboard UI glitch, non-blocking CI flakiness.

## 3. Incident Response Process

### Step 1: Detection and Triage

1. Alert fires in Datadog and triggers PagerDuty notification
2. On-call SRE acknowledges the page within the response SLA
3. SRE performs initial triage:
   - Verify the alert is not a false positive
   - Determine severity level (P1-P4)
   - Identify affected services and customer impact scope
4. Create an incident in the #incidents Slack channel using the `/incident` command:
   ```
   /incident create "Brief description" severity:P1
   ```

### Step 2: Response and Containment

**For P1 incidents:**
1. Open a war room (Zoom bridge auto-created by PagerDuty)
2. Designate roles:
   - **Incident Commander (IC):** Coordinates response, makes decisions, owns communication
   - **Technical Lead:** Drives investigation and remediation
   - **Communications Lead:** Updates status page and notifies customers
   - **Scribe:** Documents timeline, decisions, and actions in the incident channel
3. Begin containment: isolate affected systems, redirect traffic, or activate failover
4. Communicate status every **15 minutes** in the war room and on the status page

**For P2-P3 incidents:**
1. On-call SRE leads investigation
2. Pull in additional engineers as needed via Slack or PagerDuty escalation
3. Document actions in the #incidents thread
4. Communicate status every **30 minutes** for P2, hourly for P3

### Step 3: Resolution and Recovery

1. Implement fix (hotfix, configuration change, rollback, or failover)
2. Verify fix in staging (if time permits) before deploying to production
3. Monitor metrics for 30 minutes post-fix to confirm resolution
4. Update status page to "Resolved"
5. Notify affected customers via email with summary and next steps

### Step 4: Post-Mortem

Post-mortems are required for all P1 and P2 incidents and must be completed within **48 hours** (P1) or **5 business days** (P2).

#### 5 Whys Framework

All post-mortems use the **5 Whys** root cause analysis framework:

1. **Why** did the incident occur? (Proximate cause)
2. **Why** did that cause exist? (Contributing factor)
3. **Why** wasn't it caught earlier? (Detection gap)
4. **Why** didn't existing safeguards prevent it? (Prevention gap)
5. **Why** hasn't this class of issue been addressed before? (Systemic factor)

#### Post-Mortem Template

```
# Incident Post-Mortem: [INCIDENT-ID]

## Summary
- Date/Time: [Start] - [End]
- Duration: [Total duration]
- Severity: [P1/P2/P3]
- Impact: [Number of affected customers, error rates, revenue impact]

## Timeline
- [HH:MM] Alert fired
- [HH:MM] Acknowledged by [Name]
- [HH:MM] War room opened (P1 only)
- [HH:MM] Root cause identified
- [HH:MM] Fix deployed
- [HH:MM] Incident resolved

## Root Cause Analysis (5 Whys)
1. Why: ...
2. Why: ...
3. Why: ...
4. Why: ...
5. Why: ...

## Action Items
| Action | Owner | Priority | Due Date |
|--------|-------|----------|----------|
| ... | ... | ... | ... |

## Lessons Learned
- What went well:
- What could be improved:
- Where we got lucky:
```

Post-mortems are stored in Confluence under **Engineering > Incident Post-Mortems** and are accessible to all engineering staff. A **blameless culture** is maintained -- post-mortems focus on systemic improvements, not individual fault.

## 4. Escalation Paths

| Severity | First Responder | 30-min Escalation | 1-hour Escalation | 4-hour Escalation |
|---|---|---|---|---|
| **P1** | On-call SRE | VP of Engineering | CTO | CEO |
| **P2** | On-call SRE | Engineering Manager | VP of Engineering | - |
| **P3** | On-call SRE | Team Lead | Engineering Manager | - |
| **P4** | Assigned engineer | - | - | - |

### On-Call Rotation
- Primary on-call: 1-week rotation across the SRE team
- Secondary on-call: backup engineer on the same rotation, paged if primary doesn't acknowledge within 10 minutes
- Escalation to management if neither primary nor secondary responds within 20 minutes
- On-call handoff occurs every Monday at 10:00 AM ET with a 30-minute briefing

## 5. Communication Templates

### Status Page Update (P1)
```
[Investigating] We are currently investigating an issue affecting [service/feature].
Some users may experience [symptom]. Our team is actively working on resolution.
We will provide an update within 15 minutes.
```

### Customer Email (P1)
```
Subject: [Resolved/Investigating] Service disruption on [date]

Dear [Customer],

We experienced a service disruption on [date] from [start time] to [end time] UTC
that affected [description of impact].

Root cause: [Brief, non-technical explanation]
Resolution: [What was done to fix it]
Prevention: [What we're doing to prevent recurrence]

We sincerely apologize for the inconvenience. If you have questions, please contact
your account representative or support@meridian-ai.com.

Regards,
Meridian AI Systems Engineering Team
```

## 6. Tools and Access

| Tool | Purpose | Access |
|---|---|---|
| **PagerDuty** | Alerting and escalation | All on-call engineers |
| **Datadog** | Monitoring, dashboards, APM | All engineers |
| **Slack #incidents** | Real-time coordination | All engineering |
| **Status page** (Statuspage.io) | Customer-facing status | IC and Communications Lead |
| **Zoom** | War room bridge | Auto-created by PagerDuty |
| **AWS Console** | Infrastructure investigation | SRE team + break-glass for others |

## 7. Metrics and Review

The SRE team tracks the following incident metrics monthly:
- **MTTR** (Mean Time to Resolution) by severity level
- **MTTA** (Mean Time to Acknowledge)
- Number of incidents by severity
- Post-mortem completion rate (target: 100% for P1/P2)
- Action item completion rate (target: >90% within 30 days)

Incident trends are reviewed in the monthly Engineering All-Hands meeting.

---

*This plan is reviewed quarterly and tested via tabletop exercises twice per year. Next tabletop exercise: March 2026. Contact sre-team@meridian-ai.com with questions.*
