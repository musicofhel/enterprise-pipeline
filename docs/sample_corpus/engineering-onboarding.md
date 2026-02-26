# Engineering Onboarding Guide

**Document Version:** 3.0
**Effective Date:** January 20, 2026
**Owner:** Engineering Management
**Last Reviewed:** January 18, 2026
**Classification:** Internal

---

## 1. Welcome

Welcome to the Meridian AI Systems engineering team! This guide covers everything you need to get productive during your first 90 days. Your onboarding buddy and manager will be your primary points of contact throughout the process.

## 2. Week 1: Environment Setup and Orientation

### Day 1 - Administrative Setup
- [ ] Complete HR onboarding in PeopleHub (benefits enrollment, tax forms, emergency contacts)
- [ ] Pick up your equipment from IT (MacBook Pro M3, YubiKey, monitors)
- [ ] Set up Okta SSO and configure MFA with your YubiKey
- [ ] Join required Slack channels: #engineering, #deploys, #incidents, #your-team
- [ ] Review the Employee Handbook and sign the Acceptable Use Policy
- [ ] Meet your onboarding buddy (assigned by your manager before your start date)

### Day 2 - Development Environment
- [ ] Clone the monorepo: `git clone git@github.com:meridian-ai/platform.git`
- [ ] Run the setup script: `./scripts/dev-setup.sh` (installs Docker, Terraform, Python 3.11, Node 22)
- [ ] Verify local development environment with `make test-local`
- [ ] Set up IDE (VS Code with recommended extensions listed in `.vscode/extensions.json`)
- [ ] Configure Git commit signing with your YubiKey GPG key
- [ ] Request access to AWS staging account via the #infra-access Slack channel

### Day 3-5 - Codebase Orientation
- [ ] Complete the **Architecture Walkthrough** self-paced course (2 hours, in Confluence)
- [ ] Review the system architecture diagram in the Engineering Wiki
- [ ] Shadow a senior engineer during a code review session
- [ ] Read the API Documentation (public docs at docs.meridian-ai.com)
- [ ] Familiarize yourself with the CI/CD pipeline (GitHub Actions workflows in `.github/workflows/`)
- [ ] Review the Runbook index for your team's services

### Key Architecture Components
- **API Gateway:** FastAPI application behind AWS ALB, deployed on ECS Fargate
- **Vector Store:** Pinecone (production) / Chroma (local development)
- **LLM Orchestration:** Custom Python framework with LangChain for chain composition
- **Queue:** Amazon SQS for async document ingestion
- **Database:** PostgreSQL 16 on RDS (primary) + Redis 7 on ElastiCache (caching)
- **Monitoring:** Datadog APM, logs, and custom metrics
- **Infrastructure:** Terraform modules in `/infra`, deployed via GitHub Actions

## 3. Week 2: First Contributions

### Pair Programming
- Your onboarding buddy will pair with you on a **starter bug fix** selected from the `good-first-issue` label in Jira
- Starter issues are scoped to take 2-4 hours and involve well-documented areas of the codebase
- Your buddy will walk you through the full development cycle: branch, code, test, PR, review, deploy

### Development Workflow
1. Create a feature branch from `main`: `git checkout -b feat/JIRA-123-description`
2. Write code with tests (minimum 80% coverage for new code)
3. Run the linter and type checker: `make lint && make typecheck`
4. Push and open a PR with the PR template filled out
5. Request review from your buddy and one other team member
6. Address review comments; all PRs require **2 approvals** before merge
7. Merge via **squash merge** to keep the commit history clean

### Branch Naming Convention
- Features: `feat/JIRA-123-short-description`
- Bug fixes: `fix/JIRA-456-short-description`
- Hotfixes: `hotfix/JIRA-789-short-description`
- Experiments: `exp/your-name/experiment-name`

## 4. Week 3: First Pull Request

By the end of Week 3, you should submit your **first independent PR** (without pair programming). This is typically:
- A bug fix from the `good-first-issue` backlog
- A documentation improvement
- A small feature enhancement scoped by your manager

### PR Checklist
- [ ] Tests pass locally (`make test`)
- [ ] No linting errors (`make lint`)
- [ ] Type checking passes (`make typecheck`)
- [ ] PR description explains the "why" not just the "what"
- [ ] Screenshots included for UI changes
- [ ] Database migrations tested locally (if applicable)
- [ ] No secrets or credentials in the diff

## 5. Month 1-3: Growth Phase

### Code Review Mentorship
- Starting in Month 2, you'll be added to the code review rotation
- Your first 10 reviews will be **shadowed** by a senior engineer who provides feedback on your review comments
- Target: complete at least **3 code reviews per week** by the end of Month 2
- Focus areas for reviews: correctness, test coverage, security implications, performance

### Key Milestones

| Timeframe | Milestone |
|---|---|
| End of Week 1 | Local environment running, architecture understood |
| End of Week 2 | First paired PR merged |
| End of Week 3 | First independent PR submitted |
| End of Month 1 | 3+ PRs merged, SOC 2 training complete |
| End of Month 2 | On code review rotation, contributing to sprint planning |
| End of Month 3 | Independently owning features, onboarding survey completed |

### Required Training
All training must be completed within the specified timeframes:

| Training | Deadline | Platform |
|---|---|---|
| **SOC 2 Compliance** | Within **30 days** of start | KnowBe4 |
| **Secure Coding Practices** | Within 30 days | KnowBe4 |
| **Incident Response Procedures** | Within 45 days | Internal Wiki + quiz |
| **Data Privacy (GDPR/CCPA)** | Within 45 days | KnowBe4 |
| **AWS Security Fundamentals** | Within 60 days | AWS Skill Builder |

Failure to complete SOC 2 training within 30 days will result in temporary suspension of production access.

## 6. Tools and Access

| Tool | Purpose | Access Request |
|---|---|---|
| **GitHub** | Source code, PRs, CI/CD | IT provisions on Day 1 |
| **Slack** | Communication | IT provisions on Day 1 |
| **Jira** | Project management, sprint tracking | IT provisions on Day 1 |
| **Datadog** | Monitoring, APM, logs | Request via #infra-access |
| **PagerDuty** | On-call rotations (after Month 3) | Manager assigns |
| **AWS Console** | Cloud infrastructure (staging only initially) | Request via #infra-access |
| **Confluence** | Engineering wiki, runbooks, ADRs | IT provisions on Day 1 |
| **Figma** | Design specs (view-only for engineers) | IT provisions on Day 1 |
| **1Password Teams** | Secrets management for development | IT provisions on Day 1 |

## 7. On-Call

New engineers are **not** added to the on-call rotation until after their 90-day onboarding period. Before joining on-call:
- Complete the Incident Response training
- Shadow at least **2 on-call shifts** with a senior engineer
- Review all P1 and P2 post-mortems from the past 6 months
- Conduct a practice incident response with your manager

On-call rotation is **1 week every 6 weeks** for most teams. Compensation: $500/week on-call stipend + $200 per P1 incident response outside business hours.

## 8. Questions and Support

- **Onboarding buddy:** Your first point of contact for day-to-day questions
- **Manager:** Weekly 1:1s for career development, project alignment, and feedback
- **#engineering-onboarding Slack channel:** Community of current and recent new hires
- **Engineering Wiki:** https://wiki.meridian-ai.com (search before asking!)
- **People Operations:** people-ops@meridian-ai.com for HR and benefits questions

---

*This guide is updated quarterly. Feedback on the onboarding experience is collected via a survey at the end of Month 3. Contact engineering-management@meridian-ai.com with suggestions.*
