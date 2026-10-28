# Preliminary Design Review (PDR)
## Student Management System with APAAR ID

| | |
|---|---|
| **Project** | Student Management System (APAAR-based) |
| **Repository** | https://github.com/keshant-commits/Student-management-system |
| **Owner** | keshant-commits |
| **Document version** | 0.2 (Draft). See change log at the end of this document |
| **Date** | 28 October 2026 |
| **Status** | Proposed design, open for review. **Companion:** `PRD.md` holds the task plan; where the two differ, PRD Section 2 wins |

> **Note on scope.** This document proposes the design for the system whose repository structure is already in place. Items marked **[Assumption]** are design decisions or facts that should be confirmed before implementation. Numeric thresholds and rule behaviours are configurable defaults, not regulatory statements.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Background and Problem Statement](#2-background-and-problem-statement)
3. [Goals, Non-Goals and Success Criteria](#3-goals-non-goals-and-success-criteria)
4. [Stakeholders and User Roles](#4-stakeholders-and-user-roles)
5. [Scope](#5-scope)
6. [Functional Requirements](#6-functional-requirements)
7. [Non-Functional Requirements](#7-non-functional-requirements)
8. [System Architecture](#8-system-architecture)
9. [Technology Stack](#9-technology-stack)
10. [Backend Design](#10-backend-design)
11. [Data Model](#11-data-model)
12. [Validation Engine Design](#12-validation-engine-design)
13. [ML Anomaly Detection Design](#13-ml-anomaly-detection-design)
14. [Security and Privacy Design](#14-security-and-privacy-design)
15. [API Design](#15-api-design)
16. [Key Workflows](#16-key-workflows)
17. [Frontend Design](#17-frontend-design)
18. [APAAR Integration Design](#18-apaar-integration-design)
19. [DevOps, CI/CD and Deployment](#19-devops-cicd-and-deployment)
20. [Testing Strategy](#20-testing-strategy)
21. [Risks and Mitigations](#21-risks-and-mitigations)
22. [Milestones and Delivery Plan](#22-milestones-and-delivery-plan)
23. [Open Questions and Assumptions](#23-open-questions-and-assumptions)
24. [Glossary](#24-glossary)
25. [Appendix: Repository Map](#25-appendix-repository-map)

---

## 1. Executive Summary

The **Student Management System** is a web platform that manages student enrolment records using the **APAAR ID** (Automated Permanent Academic Account Registry), a unique lifelong student identifier used in India's education system.

The platform serves four groups:

- **Institutions** upload and maintain student records, individually or in bulk by CSV, and submit them to the regulator.
- **Regulator staff (AICTE-style oversight role)** monitor intake compliance, detect duplicates and anomalies across institutions, and generate reports.
- **Verifiers** (employers, universities, agencies) verify a student's record, with the student's consent.
- **Students** view their own record and control who may verify it.

The core value of the system comes from three capabilities:

1. **Data quality enforcement.** A pluggable rule engine validates every record at entry and at upload (APAAR format and registry check, duplicate detection within and across institutions, intake limits, category and date consistency).
2. **Oversight and analytics.** Dashboards, risk tables and an ML-based anomaly detector surface institutions or patterns that need review.
3. **Trusted, privacy-preserving verification.** Records are issued as **Ed25519-signed verifiable records** with QR codes, and release of personal data is gated by explicit **student consent**.

Because the real APAAR registry may not be available during development, an **adapter layer** lets the system run against a **mock APAAR service** and switch to the real one by configuration.

---

## 2. Background and Problem Statement

### 2.1 Context

India's One Nation One Student ID initiative issues each student an APAAR ID. Regulators and institutions need a reliable way to connect enrolment data to this identifier. **[Assumption]** The APAAR ID is a 12-digit numeric identifier; the exact format is held in configuration so it can be corrected without code changes.

### 2.2 Problems this system addresses

| # | Problem | Impact |
|---|---|---|
| P1 | Student data is submitted with inconsistent or incorrect identifiers | Records cannot be reconciled across institutions |
| P2 | The same student can appear twice in one institution or in several institutions | Inflated enrolment, fraudulent seat occupancy |
| P3 | Institutions may admit more students than approved intake | Compliance breaches discovered late |
| P4 | Seat categories and special (supernumerary) quotas are misreported | Distorted reservation and fee-waiver data |
| P5 | Verification of a student's record is manual, slow and easy to forge | Employers and universities cannot trust paper records |
| P6 | Sharing a student's personal data has no consent trail | Privacy and legal exposure |
| P7 | Regulators lack real-time, cross-institution visibility | Reactive instead of proactive oversight |

---

## 3. Goals, Non-Goals and Success Criteria

### 3.1 Goals

- **G1.** Provide a single system to register, validate, submit and report student enrolment keyed by APAAR ID.
- **G2.** Detect and flag data-quality and compliance problems automatically, with clear, explainable flags.
- **G3.** Give the regulator real-time visibility and anomaly detection across institutions.
- **G4.** Enable tamper-evident, consent-based verification of a student's record.
- **G5.** Protect personal data by design (field-level encryption, RBAC, audit logging, masking).
- **G6.** Be demonstrable end to end with generated data, with no dependency on live government systems.

### 3.2 Non-Goals

- Not a full ERP: no timetables, fee collection, grading, attendance or hostel modules.
- Not a replacement for the official APAAR registry. The system consumes it through an adapter.
- No mobile native apps (the web UI is responsive).
- No blockchain. Integrity is provided by digital signatures and an audit log.

### 3.3 Success Criteria

| Metric | Target |
|---|---|
| Single-record validation latency (p95) | under 300 ms with the mock registry |
| Bulk CSV of 10,000 rows processed | under 2 minutes, in a background task |
| Duplicate detection recall on seeded test data | at least 95% for exact, at least 85% for fuzzy |
| Signed record verification | 100% of tampered records rejected in tests |
| Consent enforcement | 0 personal-data releases without active consent in tests |
| Automated test coverage (backend core, security, validation) | at least 80% |

---

## 4. Stakeholders and User Roles

| Role | Description | Key goals |
|---|---|---|
| **Institution Admin** | Staff at a college or university | Add students, upload CSVs, fix flags, submit data |
| **Regulator Officer (AICTE)** | Oversight body staff | Monitor compliance, review anomalies, configure rules, export reports |
| **Regulator Admin** | Senior oversight user | Everything an officer can do, plus rule configuration, user management and audit access |
| **Verifier** | Employer, university, agency | Verify an APAAR record, request consent |
| **Student** | The enrolled person | View own record, approve or revoke consent, share QR |
| **System Admin** | Platform operator (technical) | Keys, deployment, seed data, health |

### 4.1 Permission Matrix

| Capability | Institution | Regulator Officer | Regulator Admin | Verifier | Student |
|---|:-:|:-:|:-:|:-:|:-:|
| Create or edit students (own institution) | Yes | No | No | No | No |
| Bulk upload CSV | Yes | No | No | No | No |
| View own institution's flags | Yes | No | No | No | No |
| Submit enrolment data | Yes | No | No | No | No |
| View all institutions' analytics | No | Yes | Yes | No | No |
| View anomalies and risk table | No | Yes | Yes | No | No |
| Configure validation rules | No | No | Yes | No | No |
| View audit logs | No | Read-only | Yes | No | No |
| Generate and export reports | No | Yes | Yes | No | No |
| Verify an APAAR record | No | Yes | Yes | Yes (with consent) | No |
| Request consent | No | No | No | Yes | No |
| Grant or revoke consent | No | No | No | No | Yes |
| View own record | No | No | No | No | Yes |

---

## 5. Scope

### 5.1 In Scope

- Authentication with 2FA, role-based access control, rate limiting
- Institution, program and student management
- Single-entry and CSV bulk upload with an error report
- Pluggable validation engine with configurable rules
- Intake and supernumerary tracking per institution and program
- Submission workflow (draft, submitted, locked)
- Analytics dashboards and ML-based anomaly detection
- Verifiable signed records with QR codes and public verification page
- Consent request and approval flow
- Audit logging and PDF/CSV reports
- Real-time live feed (WebSocket)
- Mock APAAR registry with generated demo data
- Docker-based local and production deployment, CI pipelines

### 5.2 Out of Scope (this phase)

- Integration with the real APAAR registry in production (adapter is ready, credentials and agreements are not)
- Payment, scholarship disbursal, hostel and examination modules
- Multi-language UI **[Assumption: English first]**

---

## 6. Functional Requirements

Priority: **M** = Must, **S** = Should, **C** = Could.

### 6.1 Authentication and Access (FR-AUTH)

| ID | Requirement | Priority |
|---|---|---|
| FR-AUTH-01 | Users log in with email and password; passwords are hashed with a modern adaptive algorithm | M |
| FR-AUTH-02 | Time-based one-time password (TOTP) 2FA is available and enforced for regulator roles | M |
| FR-AUTH-03 | Short-lived JWT access tokens with refresh tokens; logout revokes the refresh token | M |
| FR-AUTH-04 | Every endpoint declares a required role or permission through a dependency | M |
| FR-AUTH-05 | Login and sensitive endpoints are rate limited per IP and per user | M |
| FR-AUTH-06 | Account lockout after repeated failed logins, with audit entry | S |

### 6.2 Institutions and Programs (FR-INST)

| ID | Requirement | Priority |
|---|---|---|
| FR-INST-01 | Maintain institutions with code, name, state, type and status | M |
| FR-INST-02 | Maintain programs per institution with approved intake per academic year | M |
| FR-INST-03 | Maintain supernumerary seat allowances per program | M |
| FR-INST-04 | Regulator can browse, search and filter institutions with compliance status | M |

### 6.3 Student Records (FR-STU)

| ID | Requirement | Priority |
|---|---|---|
| FR-STU-01 | Create, edit, view and soft-delete a student record keyed by APAAR ID | M |
| FR-STU-02 | Sensitive fields (phone, email, date of birth, address) are encrypted at rest | M |
| FR-STU-03 | Maintain enrolment history (program, year, status changes) per student | M |
| FR-STU-04 | Every create or update runs the validation engine and stores resulting flags | M |
| FR-STU-05 | Institution users see only their own students (row-level scoping) | M |
| FR-STU-06 | Personal data is masked in lists and logs by default | M |

### 6.4 Bulk Upload (FR-UP)

| ID | Requirement | Priority |
|---|---|---|
| FR-UP-01 | Upload a CSV file through drag and drop; file size and type are checked | M |
| FR-UP-02 | Processing runs asynchronously in a background task with progress reporting | M |
| FR-UP-03 | A row-level error report is produced and downloadable | M |
| FR-UP-04 | Valid rows may be accepted while invalid rows are rejected, based on a user choice | S |
| FR-UP-05 | Each upload is recorded as an `upload_batch` with counts and status | M |
| FR-UP-06 | Sample CSVs (valid, with errors, with duplicates) are shipped for demo | M |

### 6.5 Validation and Flags (FR-VAL)

| ID | Requirement | Priority |
|---|---|---|
| FR-VAL-01 | Rules are independent classes that return zero or more flags | M |
| FR-VAL-02 | Each flag has code, severity (info, warning, error, critical), message, field and rule version | M |
| FR-VAL-03 | Regulator Admin can enable, disable and tune rules and thresholds without redeploying | M |
| FR-VAL-04 | Flags can be acknowledged, resolved with a comment, or escalated | M |
| FR-VAL-05 | Blocking flags (error, critical) prevent final submission until resolved | M |
| FR-VAL-06 | Validation results are explainable: the flag shows the matched record or the threshold exceeded | S |

### 6.6 Submission (FR-SUB)

| ID | Requirement | Priority |
|---|---|---|
| FR-SUB-01 | Institution submits an academic-year dataset when no blocking flags remain | M |
| FR-SUB-02 | Submission locks the dataset; corrections need a regulator-approved reopen | S |
| FR-SUB-03 | A submission summary is generated and recorded in the audit log | M |

### 6.7 Analytics and Anomalies (FR-AN)

| ID | Requirement | Priority |
|---|---|---|
| FR-AN-01 | Dashboards: intake utilisation gauge, state-wise map, trend lines, risk table | M |
| FR-AN-02 | ML anomaly detector scores institutions or batches and lists the top anomalies | M |
| FR-AN-03 | Each anomaly shows contributing features so reviewers understand why | S |
| FR-AN-04 | A live feed shows validation and upload events in real time | S |

### 6.8 Verification, Consent and Records (FR-VER)

| ID | Requirement | Priority |
|---|---|---|
| FR-VER-01 | A verifier lookup by APAAR ID reveals **nothing** about the person. The response is identical whether or not the ID exists (`consent_required`), and the verifier may start a consent request. Regulator roles may look up within their mandate, always audited. | M |
| FR-VER-02 | Detailed data is released only after the student grants consent | M |
| FR-VER-03 | Consent has a scope, a purpose and an expiry, and can be revoked at any time | M |
| FR-VER-04 | The system issues a signed verifiable record (Ed25519) with a QR code **only from a granted consent** (student self-share or approved verifier request) | M |
| FR-VER-05 | A public page verifies a record **by its random token only** (never by APAAR ID) and shows valid, expired or revoked plus only the consented signed claims | M |
| FR-VER-06 | Every verification and consent event is written to the audit log | M |

### 6.9 Reporting and Audit (FR-RPT)

| ID | Requirement | Priority |
|---|---|---|
| FR-RPT-01 | Generate institution compliance reports and state-level summaries (PDF and CSV) | M |
| FR-RPT-02 | Generate a student certificate with an embedded QR | S |
| FR-RPT-03 | Append-only audit log of security-relevant actions, filterable in the UI | M |
| FR-RPT-04 | Audit log entries are chained by hash so tampering is detectable | C |

### 6.10 Integration (FR-INT)

| ID | Requirement | Priority |
|---|---|---|
| FR-INT-01 | An APAAR client adapter switches between mock and real registry by configuration | M |
| FR-INT-02 | Integration endpoints expose documented APIs for external systems with API keys | S |
| FR-INT-03 | An integration guide documents contracts, errors and retry behaviour | M |

---

## 7. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Performance** | List endpoints paginate (default 50, max 200). Dashboard queries use pre-aggregation or indexed queries. |
| **Scalability** | Stateless API instances behind a load balancer. Background work offloaded to workers. |
| **Availability** | Target 99.5% for the demo or pilot deployment. Health endpoints for orchestration. |
| **Security** | See [Section 14](#14-security-and-privacy-design). OWASP ASVS Level 2 as the guiding baseline. |
| **Privacy** | Data minimisation, purpose limitation and consent aligned with India's Digital Personal Data Protection Act, 2023 **[Assumption: legal review needed]**. |
| **Auditability** | All privileged actions and all personal-data releases are logged with actor, time, IP and outcome. |
| **Usability** | Role-specific navigation, accessible components (keyboard and screen reader support), responsive layout. |
| **Maintainability** | Layered architecture, typed code (Pydantic and TypeScript), linting and formatting in CI. |
| **Observability** | Structured JSON logs, request IDs, basic metrics endpoint. |
| **Portability** | Everything runs through Docker Compose on a single machine. |
| **Data retention** | Configurable retention for logs and soft-deleted students. |

---

## 8. System Architecture

### 8.1 Context Diagram

```
             +-------------+   +-----------------+   +-----------+   +-----------+
             | Institution |   | Regulator Staff |   | Verifier  |   |  Student  |
             +------+------+   +--------+--------+   +-----+-----+   +-----+-----+
                    \                  |                   |               /
                     \                 |                   |              /
                      v                v                   v             v
                  +--------------------------------------------------------+
                  |        React + Vite Web App (role-based routes)         |
                  +----------------------------+---------------------------+
                                               | HTTPS (REST + WebSocket)
                                               v
                  +--------------------------------------------------------+
                  |                  FastAPI Backend (/api/v1)              |
                  |  Auth/RBAC | Services | Validation Engine | ML | Signing |
                  +------+-----------+-------------+-------------+---------+
                         |           |             |             |
                         v           v             v             v
                   +-----------+ +--------+ +-------------+ +-----------+
                   | PostgreSQL| | Redis  | | Celery      | | APAAR     |
                   | (data)    | | (queue | | Workers     | | adapter   |
                   |           | | cache) | | (bulk jobs) | |           |
                   +-----------+ +--------+ +-------------+ +-----+-----+
                                                                   |
                                                    +--------------+-------------+
                                                    |                            |
                                          +---------v--------+        +----------v---------+
                                          | Mock APAAR       |        | Real APAAR registry |
                                          | service (demo)   |        | (future)            |
                                          +------------------+        +--------------------+
```

### 8.2 Architectural Style

- **Layered monolith** for the backend: `api` (HTTP) -> `services` (business logic) -> `models/db` (persistence), with `validation`, `ml` and `core` as shared modules. This keeps deployment simple while keeping boundaries clear enough to split later.
- **Adapter pattern** for the APAAR registry.
- **Strategy and plugin pattern** for validation rules.
- **Task queue** for long-running work (bulk upload, report generation, model scoring).
- **Event stream** over WebSocket for the live feed.

### 8.3 Deployment View

| Container | Purpose |
|---|---|
| `backend` | FastAPI app (Uvicorn/Gunicorn) |
| `worker` | Celery worker, same image as backend |
| `frontend` | Static build served by Nginx |
| `mock-apaar-service` | Standalone FastAPI mock registry |
| `postgres` | Primary database |
| `redis` | Broker and cache |

`docker-compose.yml` is for development, `docker-compose.prod.yml` for production-like deployment (no bind mounts, tighter settings, secrets from environment).

---

## 9. Technology Stack

| Layer | Choice | Reason |
|---|---|---|
| Backend framework | **FastAPI** (Python) | Async, typed, automatic OpenAPI docs |
| ORM and migrations | **SQLAlchemy 2.x + Alembic** | Mature, migration-friendly |
| Database | **PostgreSQL** **[Assumption]** | Strong constraints, JSONB, full-text and trigram search for fuzzy matching |
| Validation schemas | **Pydantic** | Request and response typing |
| Background jobs | **Celery + Redis** **[Assumption]** | Standard for Python async jobs |
| Cryptography | `cryptography` library (AES-GCM, Ed25519), `passlib`/`argon2` for hashing, `pyotp` for TOTP | Well-reviewed primitives |
| ML | **scikit-learn** (Isolation Forest), `joblib` for model persistence | Simple, explainable baseline |
| Frontend | **React + TypeScript + Vite** | Fast dev, strong typing |
| Styling and UI | **Tailwind CSS + shadcn/ui** | Consistent, accessible components |
| Charts | A React charting library (for example Recharts) **[Assumption]** | Gauge, line, map support |
| QR codes | `qrcode` (backend) and a QR viewer component (frontend) | Offline generation |
| Testing | **pytest**, and a frontend test runner (Vitest) | Standard |
| Containers | **Docker and Docker Compose** | Reproducible environments |
| CI/CD | **GitHub Actions** | Already scaffolded in `.github/workflows` |
| Mock data | **Faker** | Realistic Indian-style names and attributes |

---

## 10. Backend Design

### 10.1 Layer Responsibilities

| Layer | Folder | Responsibility |
|---|---|---|
| Entry | `app/main.py` | App factory, middleware (CORS, request ID, rate limit), router mounting |
| API | `app/api/v1/*` | HTTP routing, request parsing, dependency injection, response shaping. No business logic. |
| Services | `app/services/*` | Business logic and orchestration. Called by API and tasks. |
| Validation | `app/validation/*` | Rule engine and rules |
| ML | `app/ml/*` | Feature extraction, training, scoring |
| Core | `app/core/*` | Config, security, encryption, signing, RBAC, rate limiting |
| Data | `app/models`, `app/db` | ORM models, sessions, seed |
| Schemas | `app/schemas/*` | Pydantic request and response models |
| Tasks | `app/tasks/*` | Celery app and background jobs |
| Utils | `app/utils/*` | CSV parsing, QR generation, masking helpers |

### 10.2 Core Modules

| Module | Design notes |
|---|---|
| `config.py` | Settings from environment variables (12-factor). Validated at startup. Holds APAAR format regex, token lifetimes, feature flags. |
| `security.py` | Password hashing, JWT creation and verification, TOTP secret generation and verification, refresh token rotation. |
| `encryption.py` | AES-256-GCM field encryption. A random 96-bit nonce per encryption, stored with the ciphertext. Key supplied through environment, with a key identifier to support rotation. |
| `signing.py` | Ed25519 sign and verify. Signs a canonical JSON serialisation of a record payload. Public key is exposed through an endpoint so anyone can verify. |
| `rbac.py` | Role and permission dependencies, for example `require_role("regulator_admin")`. Row-level scoping helpers for institution users. |
| `rate_limit.py` | Sliding-window or token-bucket limiter backed by Redis, with stricter limits for auth and verification endpoints. |

### 10.3 Service Layer

| Service | Responsibilities |
|---|---|
| `student_service` | CRUD, encryption and decryption of sensitive fields, history tracking, triggers validation |
| `upload_service` | Accept file, create batch, dispatch task, collect results, build error report |
| `apaar_client` | Adapter interface `lookup(apaar_id)` with mock and real implementations, retries, timeouts, caching |
| `consent_service` | Create, approve, deny, revoke and expire consents; check consent at data-release time |
| `record_service` | Build canonical record payload, sign it, store the verifiable record, verify on request |
| `certificate_service` | Render a student certificate with an embedded QR |
| `report_service` | Compile compliance reports and exports |
| `audit_service` | Append audit entries with actor, action, target, outcome and metadata |

### 10.4 Background Tasks

- `bulk_upload_task`: parse CSV in chunks, validate each row, batch-insert valid rows, store row-level errors, update the `upload_batch` progress, publish progress events for the live feed.
- Scheduled jobs **[Assumption]**: nightly anomaly scoring, consent expiry sweeper, retention clean-up.

### 10.5 Cross-cutting Concerns

- **Error handling:** a single exception handler returns a consistent error envelope: `{ "error": { "code", "message", "details", "request_id" } }`.
- **Idempotency:** bulk upload and submission endpoints accept an idempotency key to avoid double processing.
- **Transactions:** each service call is one unit of work. Bulk inserts use savepoints per chunk.
- **Pagination and filtering:** cursor or page-based, with allowed filters whitelisted.

---

## 11. Data Model

### 11.1 Entity Overview

A **person** (identity, one row per APAAR ID) is separate from an **enrolment** (one person in one program at one institution for a period). This lets the same person appear at two institutions, which is exactly the overlap the system must detect. See `PRD.md` Section 2.1 (decision ID-1).

```
 users ──(institution_id)──> institutions ──< programs ──< intake_allocations
   │ (person_id for students)        │              │
   ▼                                 │              │
 persons ──────────────< enrolments >┘──────────────┘
 (one per APAAR ID)         │
   │                        ├──< enrolment_status_history
   │                        ├──< validation_flags
   │                        └──  upload_batches (source)
   └──< consents ──< verifiable_records

 rules_config        audit_log (append-only)
```

### 11.2 Tables

> Types are indicative. All tables include `id` (UUID), `created_at`, `updated_at`.

**`users`**

| Column | Type | Notes |
|---|---|---|
| email | text, unique | Login identifier |
| password_hash | text | Adaptive hash (Argon2id) |
| role | enum | `institution`, `regulator_officer`, `regulator_admin`, `verifier`, `student`, `system_admin` |
| institution_id | FK, nullable | Set for institution users |
| person_id | FK, nullable | Set for student users |
| totp_secret_enc | bytea, nullable | Encrypted 2FA secret |
| is_active, failed_logins, locked_until | | Lockout support |

**`institutions`**

| Column | Type | Notes |
|---|---|---|
| code | text, unique | Official institution code |
| name, state, district, type | text | Type: university, college, etc. |
| status | enum | active, suspended |

**`programs`**

| Column | Type | Notes |
|---|---|---|
| institution_id | FK | |
| name, level, discipline | text | |
| approved_intake | int | Default sanctioned seats |
| supernumerary_allowed | int | Extra seats allowed outside intake |
| (per-year overrides) | | Stored in an `intake_allocations` table by academic year |

**`persons`** (identity, one row per APAAR ID)

| Column | Type | Notes |
|---|---|---|
| apaar_id_hash | text, nullable | Keyed HMAC-SHA256 of the APAAR ID. **Unique where not null.** Used for lookup. |
| apaar_id_enc | bytea | AES-GCM encrypted APAAR ID |
| apaar_last4 | text | Masked display only |
| identity_status | enum | `verified`, `unverified` (registry unavailable), `provisional` (no usable ID yet) |
| full_name_enc, dob_enc, phone_enc, email_enc, address_enc | bytea | AES-GCM encrypted |
| gender | enum | |
| name_search_key | text | Normalised, non-reversible key for fuzzy matching |

**`enrolments`** (institution-specific; many per person)

| Column | Type | Notes |
|---|---|---|
| person_id, institution_id, program_id | FK | |
| academic_year | text | |
| admission_date, start_date, end_date | date | `end_date` null means open |
| status | enum | enrolled, graduated, withdrawn, transferred |
| category, quota_type, is_supernumerary | | Institution-reported seat data |
| upload_batch_id | FK, nullable | Source batch |
| deleted_at | timestamp, nullable | Soft delete |

**`enrolment_status_history`**: `enrolment_id`, `from_status`, `to_status`, `effective_date`, `changed_by`, `reason`.

**`validation_flags`**

| Column | Notes |
|---|---|
| enrolment_id (nullable), person_id (nullable), upload_batch_id (nullable), row_number | A flag may belong to an enrolment, a person or an upload row |
| rule_code, rule_version | Which rule fired |
| severity | info, warning, error, critical |
| message, details (JSONB) | Details hold matched record ids or thresholds |
| state | open, acknowledged, resolved, escalated |
| resolved_by, resolution_note | |

**`upload_batches`**: `institution_id`, `uploaded_by`, `filename`, `file_hash`, `status` (queued, processing, completed, failed), `total_rows`, `valid_rows`, `error_rows`, `started_at`, `finished_at`, `error_report_path`.

**`consents`**

| Column | Notes |
|---|---|
| person_id, verifier_user_id (nullable for self-share) | Parties. A null verifier means a student self-share |
| purpose, scope (JSONB list of fields) | What may be released and why |
| status | requested, granted, denied, revoked, expired |
| requested_at, decided_at, expires_at | |

**`verifiable_records`**: `person_id`, `consent_id` (**not null**), `payload` (JSONB canonical, consented claims only), `signature`, `key_id`, `issued_at`, `expires_at`, `revoked_at`, `public_token` (random, used in QR URL).

**`rules_config`**: `rule_code`, `enabled`, `severity_override`, `params` (JSONB), `version`, `updated_by`, `updated_at`. Rule changes are versioned so older flags remain explainable.

**`audit_log`** (append-only): `actor_id`, `actor_role`, `action`, `target_type`, `target_id`, `outcome`, `ip`, `user_agent`, `metadata` (JSONB), `prev_hash`, `entry_hash`.

### 11.3 Key Constraints and Indexes

- Unique index on `persons(apaar_id_hash)` where not null (one person per APAAR ID).
- Unique partial index on `enrolments(person_id, institution_id, program_id, academic_year)` where `deleted_at IS NULL`.
- Overlap checks (same and cross institution) use date-range queries on `enrolments`, indexed on `(person_id, start_date, end_date)`.
- Index on `enrolments(institution_id, program_id, academic_year)` for intake counting (counts enrolments, not persons).
- Trigram or phonetic index on `name_search_key` for fuzzy matching **[Assumption: PostgreSQL `pg_trgm`]**.
- `audit_log` has no UPDATE or DELETE grants for the application role.
- Foreign keys use `ON DELETE RESTRICT` for regulated data.

---

## 12. Validation Engine Design

### 12.1 Concept

Each rule is a class derived from `BaseRule` and returns a list of `Flag` objects. The engine loads enabled rules (from `rules_config`), executes them in a defined order, and aggregates the results.

```
RuleContext (student data, institution, program, academic year, db session, apaar client)
        │
        ▼
   ValidationEngine.run(context)
        │   loads enabled rules + params from rules_config
        ▼
   [ apaar_format ] -> [ apaar_registry ] -> [ duplicates... ] -> [ intake... ] -> [ category/date ]
        │
        ▼
   list[Flag] -> persisted -> published to live feed
```

**Execution policy:** cheap, local rules run first. If `apaar_format` fails with a critical flag, expensive rules (registry lookup, fuzzy duplicates) are skipped for that record.

### 12.2 Rule Catalogue

| Rule | Code | Default severity | Logic |
|---|---|---|---|
| APAAR format | `APAAR_FORMAT` | critical | ID matches the configured pattern **[Assumption: 12 digits]** and passes any checksum defined by the spec |
| APAAR registry | `APAAR_REGISTRY` | error | Adapter confirms the ID exists and is active; optionally checks that name and date of birth match registry data |
| Duplicate, same institution | `DUP_SAME_INST` | error / warning | The same person has overlapping active enrolments in the same institution. Error for the same program, warning for a different program |
| Duplicate, cross institution | `DUP_CROSS_INST` | critical | The same person has `enrolled` enrolments in two institutions with overlapping periods, after a configurable grace period for transfers. The flag shown to an institution does not reveal the other institution's details |
| Duplicate, fuzzy | `DUP_FUZZY` | warning | Compares persons: a different or provisional person with a similar name, same date of birth and matching guardian or contact details. Similarity score above the configured threshold. |
| Intake exceeded | `INTAKE_EXCEEDED` | error | Admitted count for the program and year exceeds approved intake plus allowed supernumerary seats |
| Supernumerary misuse | `SUPERNUMERARY` | warning | Supernumerary admissions exceed the allowed count or are tagged without an eligible category |
| Category consistency | `CATEGORY_CONSISTENCY` | warning | Category and quota combinations are invalid or do not match program rules |
| Date checks | `DATE_CHECKS` | error | Admission date in the future, before the minimum plausible age, outside the academic year, or after graduation date |

### 12.3 Flag Lifecycle

```
open ──> acknowledged ──> resolved
  │
  └────> escalated ──> resolved (by regulator)
```

- **Blocking severities** (error, critical) stop submission until resolved.
- A resolved flag keeps its history (who, when, note).
- If a rule version changes, previously raised flags retain their original `rule_version`.

### 12.4 Performance Notes

- Registry lookups are cached per APAAR ID for a short TTL.
- Bulk mode batches registry calls and precomputes duplicate keys with set operations instead of per-row queries.
- Intake counting uses a single grouped query per program and year, then increments in memory while processing the batch.

---

## 13. ML Anomaly Detection Design

### 13.1 Purpose

Rules catch known problems. The anomaly detector highlights **unusual patterns** that no rule describes, for example an institution whose admissions spike just before a deadline.

### 13.2 Approach

- **Model:** Isolation Forest **[Assumption]**, an unsupervised method that suits unlabelled data. Persisted with `joblib` in `app/ml/models/`.
- **Unit of analysis:** institution-program-year and upload batch.
- **Features (`features.py`):**
  - Intake utilisation ratio
  - Share of records with open flags, by severity
  - Duplicate flag rate, cross-institution matches per 1,000 students
  - Share of supernumerary admissions
  - Admission date clustering (fraction in the last N days before cut-off)
  - Category mix deviation from the state or national average
  - Batch size relative to the institution's history
  - Registry mismatch rate
- **Training (`train_anomaly.py`):** reads aggregated features, fits the model, stores version and metrics.
- **Scoring (`anomaly_detector.py`):** produces an anomaly score and the top contributing features (for example via per-feature deviation from the median) so reviewers see *why*.

### 13.3 Governance

- An anomaly is a **review prompt, not a verdict**. It never blocks or penalises automatically.
- Scores and model versions are stored so that results can be reproduced.
- Reviewer decisions (true or false positive) are recorded to support future supervised improvement.
- Demo data from `generate_data.py` includes injected anomalies so the detector has something to find.

---

## 14. Security and Privacy Design

### 14.1 Threat Model Summary

| Threat | Mitigation |
|---|---|
| Credential stuffing, brute force | Rate limiting, lockout, 2FA, breached-password check **[Could]** |
| Token theft | Short-lived access tokens, refresh rotation, HTTPS only, secure cookie options if cookies are used |
| Broken access control | Central RBAC dependencies, row-level institution scoping, tests per role (`test_rbac.py`) |
| Personal data exposure from the database | AES-GCM field encryption, key outside the database, masking in API and logs |
| Forged or altered records | Ed25519 signatures over canonical payloads, public verification |
| Replay or reuse of verification links | Random public tokens, expiry, revocation, rate limits |
| Unauthorised data sharing | Consent gate enforced in the service layer, not only in the UI |
| Tampering with audit history | Append-only table, restricted DB permissions, hash chaining |
| Injection (SQL, CSV formula) | ORM with parameters, strict schemas, CSV cells sanitised on export |
| Malicious uploads | Size and MIME limits, parse in a worker, no execution of content, virus scan hook **[Could]** |
| Secret leakage | Secrets only from environment or secret store, `.env` ignored by Git, `.env.example` has placeholders |

### 14.2 Authentication

- Password hashing with Argon2id (or bcrypt with a suitable cost) **[Assumption]**.
- JWT access token lifetime: 15 minutes. Refresh token: 7 days, rotated on use, revocable.
- TOTP 2FA with backup codes. Mandatory for regulator roles.

### 14.3 Encryption

- **In transit:** TLS everywhere outside local development.
- **At rest (fields):** AES-256-GCM, unique nonce per value, key ID stored with ciphertext, supports rotation by re-encrypting in a background task.
- **Searchability:** encrypted fields cannot be searched directly. Dedicated non-reversible keys (for example a keyed hash of the APAAR ID or a normalised name key) support lookup and fuzzy checks without exposing plaintext.
- **Key management:** keys come from environment variables in development and from a secret manager in production **[Assumption]**.

### 14.4 Digital Signatures and Verifiable Records

1. `generate_keys.sh` creates an Ed25519 key pair. The private key stays on the server (secret). The public key is published at a well-known endpoint.
2. A record is issued **only from a granted consent**. For each record, `record_service` builds a **canonical JSON payload** (sorted keys, fixed encoding) containing minimal verified facts: APAAR ID (or a masked form), institution, program, status, issue and expiry time, and a unique record ID.
3. The payload is signed, then stored with the signature and `key_id`.
4. A QR code encodes a URL with a random `public_token` (at least 128 bits). Scanning opens `PublicVerify`, which accepts **only the token**, re-verifies the signature, checks expiry and revocation, and shows valid, expired or revoked with the consented claims. Unknown, malformed and expired tokens give a generic response.
5. Key rotation is supported through `key_id`. Old public keys stay available for verification.

### 14.5 Disclosure Tiers and Consent Model

| Tier | Who | What they learn | Basis |
|---|---|---|---|
| 0. Signed record page | Anyone with the token or QR | Valid, expired or revoked, plus only the claims in that signed record | Student consent given when the record was created |
| 1. Verifier lookup | Logged-in verifier | Nothing about the person (`consent_required`, identical for existing and non-existing IDs) | None released |
| 2. Detailed release | Verifier with active consent | Only the fields in scope, for the stated purpose, until expiry | Explicit, scoped, time-limited consent |
| Regulator access | Regulator roles | Records within their mandate | Statutory authority **[Assumption: confirm with legal]**, always audited |

Consent details:


| Element | Design |
|---|---|
| Request | Verifier states purpose and requested fields |
| Decision | Student grants (possibly narrower scope), denies, or ignores (auto-expires) |
| Enforcement | `consent_service.assert_active(person, verifier, scope)` is called by any code path that releases personal data |
| Duration | Time-limited, default **[Assumption]** 30 days, shorter for sensitive scopes |
| Revocation | Immediate. Subsequent calls fail, and records issued from that consent are revoked at once. |
| Evidence | Every state change is in `audit_log` with timestamps |
| Self-share | A student can create a consent and record for themselves (scope, purpose, expiry) without a verifier request |
| Cascade | Revoking a consent revokes the records created from it immediately |

### 14.6 Data Minimisation and Masking

- Lists show masked values by default (for example `XXXXXXXX1234`).
- Full values need an explicit permission, and the access is logged.
- Verification responses contain the minimum fields needed for the stated purpose.

### 14.7 Audit Logging

Logged events include: login success and failure, 2FA events, role or rule changes, uploads, submissions, flag resolutions, consent events, verifications, record issue and revoke, exports, and any decryption of full personal data.

### 14.8 Privacy Compliance Notes **[Assumption: legal review required]**

- Lawful basis and notice for processing student data to be defined with the deploying authority.
- Support for access, correction and erasure requests within legal limits (soft delete plus retention policy).
- Special care for data of minors (guardian consent flows may be needed).
- Breach response plan and logging of incidents.

---

## 15. API Design

### 15.1 Conventions

- Base path: `/api/v1`
- JSON over HTTPS. Auth by `Authorization: Bearer <token>`.
- Pagination: `?page=1&page_size=50`. Filters as query parameters.
- Errors: consistent envelope with `code`, `message`, `details`, `request_id`.
- OpenAPI schema auto-generated by FastAPI and summarised in `docs/api-spec.md`.

### 15.2 Endpoint Groups

| Group (file) | Representative endpoints | Roles |
|---|---|---|
| **auth** | `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/2fa/setup`, `POST /auth/2fa/verify`, `GET /auth/me` | public / authenticated |
| **institutions** | `GET /institutions`, `GET /institutions/{id}`, `POST /institutions`, `PATCH /institutions/{id}`, `GET /institutions/{id}/programs` | regulator, institution (own) |
| **students** | `GET /students`, `POST /students`, `GET /students/{id}`, `PATCH /students/{id}`, `DELETE /students/{id}`. A combined view of a person plus the institution's enrolment; `POST` creates or reuses the person (by APAAR hash) and creates an enrolment | institution (own) |
| **uploads** | `POST /uploads` (CSV), `GET /uploads`, `GET /uploads/{id}`, `GET /uploads/{id}/errors` | institution |
| **validation** | `POST /validation/check` (dry run), `GET /validation/flags`, `PATCH /validation/flags/{id}`, `GET/PUT /validation/rules` | institution (flags), regulator admin (rules) |
| **submissions** | `GET /submissions`, `POST /submissions`, `POST /submissions/{id}/reopen` | institution, regulator |
| **analytics** | `GET /analytics/overview`, `/analytics/intake`, `/analytics/states`, `/analytics/trends`, `/analytics/anomalies`, `/analytics/risk` | regulator |
| **verification** | `POST /verify/lookup` (non-disclosing, returns `consent_required`), `POST /verify/consent-requests`, `GET /verify/consent-requests`, `POST /verify/consent-requests/{id}/decision` | verifier, student |
| **records** | `POST /records/self-share`, `POST /records/issue` (from a granted consent), `GET /records/public/{token}` (public, token only), `POST /records/{id}/revoke`, `GET /records/public-key` | student, verifier, public (token read only) |
| **reports** | `POST /reports`, `GET /reports/{id}`, `GET /reports/{id}/download` | regulator, institution (own) |
| **integration** | `GET /integration/health`, `POST /integration/apaar/lookup`, API-key managed endpoints | external systems |
| **audit** | `GET /audit`, `GET /audit/{id}` | regulator |
| **ws** | `WS /ws/live` | regulator (and institution for own events) |

### 15.3 Example Contract

**Create student** `POST /api/v1/students`

Request:
```json
{
  "apaar_id": "123456789012",
  "full_name": "Asha Verma",
  "date_of_birth": "2006-04-18",
  "gender": "F",
  "category": "GEN",
  "program_id": "b6f1...",
  "academic_year": "2026-27",
  "admission_date": "2026-08-05",
  "phone": "9XXXXXXXXX",
  "email": "asha@example.com"
}
```

Response `201`:
```json
{
  "id": "5d2c...",
  "apaar_id": "XXXXXXXX9012",
  "status": "enrolled",
  "flags": [
    { "code": "DUP_FUZZY", "severity": "warning", "message": "Similar record found", "state": "open" }
  ]
}
```

---

## 16. Key Workflows

### 16.1 Single Student Entry

```
Institution user -> POST /students
   -> RBAC + schema validation
   -> student_service: encrypt fields, compute search keys
   -> ValidationEngine.run()  (APAAR format -> registry -> duplicates -> intake -> category/date)
   -> persist student + flags
   -> audit_service.log, WS event
   -> response with flags
```

### 16.2 Bulk Upload

```
User drops CSV -> POST /uploads
   -> size/type check, file hash, create upload_batch (queued)
   -> Celery: bulk_upload_task
        parse in chunks -> validate rows -> insert valid -> record errors
        progress events -> WS
   -> batch completed -> user downloads error report -> fixes and re-uploads
```

### 16.3 Submission

```
User opens Submission page -> sees summary (counts, open flags)
   -> if blocking flags exist: submission disabled, links to Flags page
   -> else POST /submissions -> dataset locked -> audit entry -> regulator dashboard updates
```

### 16.4 Consent-Based Verification

```
Verifier -> RequestConsent (APAAR ID, purpose, fields)
   -> student notified -> student opens MyRecord -> reviews -> Grant / Deny
   -> on Grant (or student self-share): record_service signs consented claims only -> QR + link
   -> verifier (or third party) opens link -> PublicVerify
        -> fetch record -> verify signature -> check expiry/revocation -> VALID / INVALID
   -> all steps audited
```

### 16.5 Anomaly Review

```
Nightly job -> compute features -> score -> store anomalies
Regulator opens Anomalies page -> inspects contributing features and linked flags
   -> mark: confirmed / false positive / needs inspection -> audit entry
```

---

## 17. Frontend Design

### 17.1 Structure

- **Routing:** `routes.tsx` defines routes per role. `ProtectedRoute.tsx` enforces authentication and role.
- **State:** `AuthContext` holds user and token state. Server data is fetched through the `api/` modules, using an HTTP client with interceptors for token refresh and error handling.
- **Hooks:** `useAuth` for session, `useLiveFeed` for WebSocket events with automatic reconnect.
- **Components:** `ui/` (shadcn primitives), `layout/`, `charts/`, `students/`, `upload/`, `verification/`.

### 17.2 Pages by Role

| Role | Pages |
|---|---|
| Institution | Dashboard, Student List, Add Student, Bulk Upload, Flags, Submission |
| Regulator | Dashboard, Institutions, Anomalies, Reports, Rules Config, Audit Logs |
| Verifier | Verify APAAR, Request Consent |
| Student | My Record (view, consent decisions, QR) |
| Public | Login, Public Verify (QR landing) |

### 17.3 UX Principles

- Role-appropriate navigation, with no dead links to forbidden pages.
- Flags are shown as colour-coded **and** icon- or text-labelled badges (not colour alone).
- Bulk upload shows progress, a summary and a sortable, downloadable error table.
- Sensitive values masked with an explicit "reveal" action that is logged.
- Charts have table or text alternatives for accessibility.
- The public verification page is simple and unambiguous: a clear VALID or INVALID state, with reasons.

---

## 18. APAAR Integration Design

### 18.1 Adapter Interface

```python
class ApaarClient(Protocol):
    async def lookup(self, apaar_id: str) -> ApaarRecord | None: ...
    async def health(self) -> bool: ...
```

- `MockApaarClient` calls `mock-apaar-service`.
- `RealApaarClient` is a stub to be completed when credentials and the contract are available.
- Selection is via configuration, for example `APAAR_MODE=mock|real`.

### 18.2 Behaviour

| Aspect | Design |
|---|---|
| Timeouts | Short timeout with limited retries and exponential backoff |
| Failure mode | If the registry is unavailable, `APAAR_REGISTRY` raises an **"unverified"** warning instead of a hard failure, and the record is queued for re-check |
| Caching | Short-lived cache of lookups, invalidated on demand |
| Privacy | Only the fields needed for validation are requested and stored |
| Contract | Documented in `docs/integration-guide.md` |

### 18.3 Mock Service

- `mock-apaar-service/main.py` is a small FastAPI app exposing lookup and health endpoints.
- `generate_data.py` uses Faker to produce `data/apaar_sample.json`, including edge cases (inactive IDs, mismatched names, duplicates across institutions) so every validation rule has demo data.

---

## 19. DevOps, CI/CD and Deployment

### 19.1 Environments

| Environment | Purpose |
|---|---|
| Local | `docker compose up`, mock APAAR, seeded demo data |
| CI | Ephemeral containers for tests |
| Staging / demo | Production-like compose, demo data |
| Production | Hardened compose or orchestrator, real secrets, backups |

### 19.2 CI Pipelines (`.github/workflows`)

| Workflow | Steps |
|---|---|
| `backend-ci.yml` | Install dependencies, lint (ruff or flake8), type check, run `pytest` with coverage, build Docker image |
| `frontend-ci.yml` | Install, lint, type check (`tsc`), unit tests, production build |
| `deploy.yml` | On tagged release: build and push images, deploy to the target environment, run smoke tests |

`PULL_REQUEST_TEMPLATE.md` requires a description, linked issue, test evidence and a security checklist.

### 19.3 Configuration and Secrets

- `.env.example` documents every variable with safe placeholders.
- Real `.env` files and the `keys/` directory are Git-ignored.
- Production secrets come from the platform's secret store.

### 19.4 Developer Experience

| Command | Action |
|---|---|
| `make up` | Start all services |
| `make migrate` | Run Alembic migrations |
| `make seed` | Load demo data (`scripts/seed_demo.sh`) |
| `make test` | Run backend and frontend tests |
| `scripts/setup.sh` | First-time setup |
| `scripts/generate_keys.sh` | Create the Ed25519 key pair |

### 19.5 Backup and Recovery

- Daily database backups with tested restore procedure.
- Documented recovery point and time objectives, for example RPO 24h and RTO 4h **[Assumption]**.

---

## 20. Testing Strategy

| Level | Scope | Tools |
|---|---|---|
| **Unit** | Rules, encryption, signing, masking, CSV parsing | pytest |
| **Service/Integration** | Services with a real test database, APAAR mock, Celery in eager mode | pytest, test containers |
| **API** | Endpoint behaviour per role, status codes, error envelope | pytest + HTTP test client |
| **Security** | RBAC matrix, consent enforcement, tampered signature rejection, rate limits | pytest |
| **Frontend** | Components, route guards, forms | Vitest, Testing Library |
| **End to end** | Login -> upload -> flags -> submit -> verify | Playwright **[Could]** |
| **Performance** | Bulk upload and dashboard queries on synthetic large data | Locust or k6 **[Could]** |

**Existing test files in the repo plan:**

| File | Verifies |
|---|---|
| `test_auth.py` | Login, tokens, 2FA, lockout |
| `test_rbac.py` | Every role against every protected endpoint group |
| `test_validation_rules.py` | Each rule's positive and negative cases |
| `test_duplicates.py` | Same-institution, cross-institution and fuzzy duplicate logic |
| `test_intake_exceeded.py` | Intake and supernumerary arithmetic, boundary cases |
| `test_signing.py` | Sign and verify, tamper detection, key rotation |
| `test_consent_flow.py` | Request, grant, deny, expire, revoke, enforcement |

**Quality gates:** merge requires passing CI and at least 80% coverage on `core`, `validation` and `services`.

---

## 21. Risks and Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Real APAAR contract or format differs from assumptions | High | High | Config-driven format, adapter pattern, early review of the official specification |
| R2 | Legal and privacy obligations are underestimated | Medium | High | Privacy review before any real data, data minimisation, consent by design |
| R3 | False positives in fuzzy duplicate detection annoy users | High | Medium | Tunable thresholds, warning severity, reviewer feedback loop |
| R4 | Encrypted fields make search and reporting hard | Medium | Medium | Separate searchable keys, aggregate tables, report on non-sensitive fields |
| R5 | Bulk upload performance issues | Medium | Medium | Chunked processing, set-based duplicate checks, load tests |
| R6 | Key loss or compromise | Low | High | Secret manager, rotation procedure, key IDs, backup of keys |
| R7 | Anomaly model mistaken for a verdict | Medium | High | UI wording, human-in-the-loop, no automatic penalties |
| R8 | Scope creep into ERP features | Medium | Medium | Non-goals in this document, change control |
| R9 | Demo data mistaken for real data | Low | Medium | Clear "DEMO" labelling and synthetic-only seed data |
| R10 | Dependency vulnerabilities | Medium | Medium | Dependabot, pinned versions, CI scans |

---

## 22. Milestones and Delivery Plan

Durations are estimates for a small team.

| Phase | Deliverables | Est. duration |
|---|---|---|
| **0. Foundation** | Repo scaffold (done), Docker Compose, config, DB session, Alembic baseline, CI skeleton | 1 week |
| **1. Identity and access** | Users, auth, JWT, 2FA, RBAC, rate limit, audit log basics, login UI | 2 weeks |
| **2. Core data** | Institutions, programs, students, encryption, enrolment history, CRUD UI | 2 weeks |
| **3. Mock APAAR and validation v1** | Mock service, adapter, engine, APAAR and duplicate rules, flags UI | 2 weeks |
| **4. Bulk upload** | CSV parsing, Celery task, error report, sample data, upload UI | 1.5 weeks |
| **5. Compliance rules and submission** | Intake, supernumerary, category and date rules, rules config UI, submission flow | 2 weeks |
| **6. Analytics and ML** | Dashboards, live feed, anomaly features, training, scoring, anomaly UI | 2.5 weeks |
| **7. Verification** | Signing, records, QR, consent flow, public verify page, student and verifier UIs | 2.5 weeks |
| **8. Reports and hardening** | Reports and certificates, security review, performance tests, documentation, demo script | 2 weeks |
| **9. Pilot readiness** | Staging deployment, backup tests, user feedback, bug fixing | 1.5 weeks |

**Total estimate:** about 19 weeks. Phases 6 and 7 can run in parallel with enough people.

### 22.1 Definition of Done (per feature)

- Requirement ID(s) traced in the PR
- Unit and integration tests pass
- RBAC and audit logging verified
- API documented, UI accessible
- No new high-severity findings from lint or dependency scans

---

## 23. Open Questions and Assumptions

| # | Question or assumption | Owner | Needed by |
|---|---|---|---|
| Q1 | Official APAAR ID format, any checksum, and registry API contract | Product / Integration | Phase 3 |
| Q2 | Which regulator rules (intake, supernumerary categories, reservation categories) apply, and where are the official tables sourced? | Product / Domain expert | Phase 5 |
| Q3 | Is institution-to-regulator submission annual, per intake round, or continuous? | Product | Phase 5 |
| Q4 | Student onboarding: how do students get accounts (invitation, OTP against registered mobile)? | Product / Security | Phase 7 |
| Q5 | Legal basis, retention periods and minors' consent requirements | Legal | Before real data |
| Q6 | Hosting environment and secret manager | DevOps | Phase 9 |
| Q7 | Default consent duration and allowed scopes | Product / Legal | Phase 7 |
| Q8 | Required report formats and templates | Regulator users | Phase 8 |
| Q9 | Database choice (PostgreSQL assumed) and extension availability (`pg_trgm`) | Engineering | Phase 2 |
| Q10 | Language support beyond English | Product | Later |

---

## 24. Glossary

| Term | Meaning |
|---|---|
| **APAAR ID** | Automated Permanent Academic Account Registry identifier assigned to a student |
| **AICTE** | All India Council for Technical Education, the regulator context for this project |
| **Intake** | Number of seats approved for a program in an academic year |
| **Supernumerary seats** | Additional seats allowed outside the approved intake for specified categories |
| **Flag** | A validation finding attached to a record or an upload row |
| **Verifiable record** | A digitally signed statement about a student that anyone can check |
| **Consent** | A student's time-limited, purpose-bound permission to release data to a verifier |
| **AES-GCM** | Authenticated symmetric encryption used for field-level encryption |
| **Ed25519** | Modern digital signature algorithm |
| **TOTP** | Time-based one-time password used for two-factor authentication |
| **RBAC** | Role-based access control |
| **Isolation Forest** | Unsupervised algorithm for detecting outliers |
| **DPDP Act** | India's Digital Personal Data Protection Act, 2023 |

---

## 25. Appendix: Repository Map

How the repository folders map to this design:

| Path | Design section |
|---|---|
| `backend/app/core/` | 10.2, 14 |
| `backend/app/api/v1/` | 15 |
| `backend/app/services/` | 10.3, 16 |
| `backend/app/validation/` | 12 |
| `backend/app/ml/` | 13 |
| `backend/app/models/`, `db/` | 11 |
| `backend/app/tasks/` | 10.4, 16.2 |
| `backend/app/utils/` | 10.1 |
| `backend/tests/` | 20 |
| `mock-apaar-service/` | 18 |
| `frontend/src/` | 17 |
| `sample-data/` | 6.4, 18.3 |
| `docs/` | Detailed documents derived from this PDR: `architecture.md` (Sections 8 to 10), `database-schema.md` (11), `api-spec.md` (15), `validation-rules.md` (12), `security-and-privacy.md` (14), `integration-guide.md` (18), `demo-script.md` (16) |
| `scripts/` | 19.4 |
| `.github/` | 19.2 |
| `docker-compose*.yml`, `Makefile` | 8.3, 19 |

---

*End of document.*

---

## Change Log

| Version | Date | Change |
|---|---|---|
| 0.1 | 28 Oct 2026 | Initial draft |
| 0.2 | 28 Oct 2026 | Split `students` into `persons` and `enrolments` so one person can be enrolled at several institutions and cross-institution overlaps can be detected. Reconciled public verification with consent by introducing disclosure tiers; verifier lookup no longer discloses existence; records require consent and are fetched by token only. Added companion `PRD.md` with task IDs and acceptance criteria. |
