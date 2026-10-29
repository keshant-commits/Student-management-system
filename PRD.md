# Product Requirements and Task Plan (PRD)
## Student Management System with APAAR ID

| | |
|---|---|
| **Version** | 0.1 (Draft) |
| **Date** | 28 October 2026 |
| **Companion document** | `PDR.md` v0.2 (design). **If the PDR and this PRD conflict, Section 2 of this PRD wins.** |
| **Purpose** | Turn the design into small, executable, verifiable tasks with acceptance criteria |

---

## 1. How to Use This Document

### 1.1 Working Rules (one task per cycle)

1. **Pick exactly one task** whose dependencies are Done and whose blocking decisions (Section 3) are Confirmed.
2. **Write the tests first** (or alongside). Every task lists its required tests, including security tests where relevant.
3. **Implement only what the acceptance criteria require.** Anything extra becomes a new task.
4. **Open one pull request per task.** The PR title starts with the task ID, for example `T-033: APAAR format rule`.
5. **Verify** every acceptance criterion with evidence (test name, command output or screenshot) in the PR description.
6. **Merge only when** CI passes and the Definition of Done (Section 1.3) is met.
7. **Update the task status** in Section 5.

### 1.2 Task Size Guide

A task should fit in one focused cycle (roughly half a day to two days for one developer). If a task is larger, split it before starting.

### 1.3 Definition of Done (applies to every task)

- [ ] All acceptance criteria met and demonstrated
- [ ] Automated tests added and passing in CI
- [ ] Required security tests added (where the task lists them)
- [ ] No secrets or real personal data committed
- [ ] RBAC and audit logging verified where the task touches protected data
- [ ] API changes reflected in `docs/api-spec.md`; schema changes have an Alembic migration
- [ ] Lint and type checks pass

### 1.4 Task Format

```
T-xxx  Title                                         [Size] [Depends on] [Blocked by decisions]
  Goal:        one sentence
  Acceptance:  testable criteria (AC1, AC2, ...)
  Tests:       required tests (U = unit, I = integration, S = security, E = end to end)
```

Requirement IDs (FR-xxx) refer to `PDR.md` Section 6.

---

## 2. Design Decisions That Override or Clarify the PDR

These resolve the two issues raised in design review. Both must be reflected in the database schema and verification API before those tasks start.

### 2.1 Decision ID-1: Student identity versus enrolment

**Problem.** The PDR made `students.apaar_id` unique among active records. That prevents the system from storing the same person enrolled at two institutions, which is exactly the case it must detect.

**Decision.** Separate *who a person is* from *where they are enrolled*.

| Concept | Table | Meaning | Uniqueness |
|---|---|---|---|
| **Person** | `persons` | One real individual, identified by APAAR ID. Holds identity and personal data. | One row per APAAR ID (`apaar_id_hash` unique where not null) |
| **Enrolment** | `enrolments` | One person's enrolment in one program at one institution for a period. Holds institution-specific data. | Many per person. Constraints below. |

**`persons`** (key columns)

| Column | Notes |
|---|---|
| `id` | UUID, internal key |
| `apaar_id_hash` | Keyed HMAC-SHA256 of the APAAR ID using a server-side secret ("pepper"). Used for lookup and uniqueness. Nullable. |
| `apaar_id_enc` | AES-GCM encrypted APAAR ID |
| `apaar_last4` | For masked display only |
| `identity_status` | `verified` (confirmed by registry), `unverified` (format ok, registry unavailable), `provisional` (no usable APAAR ID yet) |
| `full_name_enc`, `dob_enc`, `phone_enc`, `email_enc`, `address_enc` | Encrypted personal data |
| `name_search_key` | Normalised, non-reversible key for fuzzy matching |

**`enrolments`** (key columns)

| Column | Notes |
|---|---|
| `id`, `person_id` (FK), `institution_id` (FK), `program_id` (FK) | |
| `academic_year`, `admission_date`, `start_date`, `end_date` (nullable = open) | |
| `status` | `enrolled`, `graduated`, `withdrawn`, `transferred` |
| `category`, `quota_type`, `is_supernumerary` | Institution-reported seat data |
| `upload_batch_id` (nullable), `deleted_at` (nullable) | |

**Constraints and rules**

| Rule | Implementation |
|---|---|
| One person per APAAR ID | Unique index on `persons.apaar_id_hash` where not null |
| No exact duplicate enrolment | Unique partial index on `(person_id, institution_id, program_id, academic_year)` where `deleted_at IS NULL` |
| Same-institution overlap (`DUP_SAME_INST`) | Same person, same institution, overlapping active date ranges. **Error** if same program, **warning** if different program (dual-degree is possible). |
| Cross-institution overlap (`DUP_CROSS_INST`) | Same person has `enrolled` status in two different institutions with overlapping date ranges, after allowing a configurable grace period `overlap_grace_days` **[Assumption: default 30, for transfers]**. **Critical.** |
| Fuzzy duplicate (`DUP_FUZZY`) | Operates across `persons` (for example a provisional person that resembles a verified one). Warning only. Merging persons is **out of scope** for the first release; the flag links the two records for human review. |
| Missing or invalid APAAR ID | Row is stored with a `provisional` person and a blocking flag. It is never silently dropped. |
| Intake counting | Counts `enrolments` per program and academic year (not persons). |

**Consequences for other tables.** `users.student_id` becomes `users.person_id`. `consents` and `verifiable_records` reference `person_id`. `validation_flags` references `enrolment_id` and/or `person_id`. `enrolment_history` becomes `enrolment_status_history` (per enrolment). The REST resource `/students` is retained as a combined view of person plus enrolment for the institution UI.

### 2.2 Decision VER-1: Public verification and consent

**Problem.** The PDR allowed anyone to look up minimal facts about an APAAR ID *and* required consent for data release. Looking up even "exists and is active" reveals enrolment, and allows enumeration.

**Decision.** Disclosure has three tiers. **Nothing about a person is revealed to an unauthenticated or non-consented party, except what the person has explicitly chosen to put in a signed record.**

| Tier | Who | What they can learn | Consent basis |
|---|---|---|---|
| **Tier 0: Signed record page** | Anyone holding a record link or QR (no login) | Whether the record is **valid, expired or revoked**, plus only the claims inside that signed record | The student created or approved that record, so consent exists at **issue time**. The random public token acts as a bearer capability for that one record. |
| **Tier 1: Verifier lookup** | Logged-in verifier | **Nothing about the person.** The response is the same whether or not the APAAR ID exists: `consent required`. It starts a consent request if the verifier asks. | None released |
| **Tier 2: Detailed release** | Verifier with an active consent | Only the fields in the consent scope, for the stated purpose, until expiry | Explicit, scoped, time-limited student consent |
| **Regulator access** | Regulator roles | Records within their oversight mandate | Statutory authority **[Assumption: confirm with legal, see D-11]**. Always audited. |

**Rules**

1. A `verifiable_record` **cannot exist without a `consent_id`** (the column is not nullable). Consent comes either from a **student self-share** or from the student approving a **verifier request**.
2. The signed payload contains only the consented claims, with the APAAR ID masked unless the consent scope explicitly includes the full value.
3. Public tokens have at least 128 bits of randomness, an expiry, and are rate limited. Verification responses for invalid, unknown and expired tokens are indistinguishable in timing and shape except for the fixed status text.
4. **Revoking consent revokes the record immediately.** The public page then shows `revoked`.
5. The public endpoint never accepts an APAAR ID as input. It accepts only the token.
6. Every Tier 0, 1 and 2 access is written to the audit log (token verifications are logged with a hashed token reference).

**PDR requirements changed by this decision:** FR-VER-01 (verifier lookup returns no personal facts), FR-VER-04 (record requires consent), FR-VER-05 (public page by token only).

### 2.3 Other Clarifications

| # | Clarification |
|---|---|
| C-1 | APAAR ID is **not treated as public**. It is hashed for lookup, encrypted at rest and masked in the UI. |
| C-2 | Validation never silently drops data. Anything it cannot accept becomes a flag or a row-level error. |
| C-3 | An anomaly is a review prompt. It never blocks, penalises or changes data automatically. |
| C-4 | When the APAAR registry is unavailable, the system records `identity_status = unverified`, raises a warning flag and re-checks later. It does not block data entry. |

---

## 3. Decisions to Confirm Before Implementation

Status values: **Proposed** (default to use unless changed), **Confirmed**, **Rejected**. A task marked "Blocked by Dxx" must not start until that decision is **Confirmed**.

| ID | Decision | Proposed default | Status | Blocks |
|---|---|---|---|---|
| D-01 | Database | PostgreSQL 15+ with `pg_trgm` | Proposed | T-003, T-022 |
| D-02 | APAAR ID format and checksum | 12 digits, no checksum (configurable) | Proposed | T-033 |
| D-03 | Background jobs | Celery with Redis | Proposed | T-042 |
| D-04 | Identity model (Section 2.1) | As written above | Proposed | T-022 onward |
| D-05 | Verification disclosure tiers (Section 2.2) | As written above | Proposed | T-070 onward |
| D-06 | Password hashing | Argon2id | Proposed | T-010 |
| D-07 | Consent defaults | Default 30 days, max 365 days, scopes: `identity`, `enrolment`, `program`, `status` | Proposed | T-071 |
| D-08 | Student account onboarding | Invitation by institution, then OTP to registered mobile or email | Proposed | T-076 |
| D-09 | Source of intake, supernumerary and category rules | Config tables seeded from official documents supplied by the product owner | Proposed | T-050, T-051, T-052 |
| D-10 | Token transport in the browser | Access token in memory, refresh token in an `HttpOnly`, `Secure`, `SameSite` cookie | Proposed | T-011, F-001 |
| D-11 | Regulator access without consent | Allowed within mandate, audited, legal confirmation needed | Proposed | T-075 |
| D-12 | Overlap grace period | 30 days | Proposed | T-036 |
| D-13 | Data retention periods | Audit log 7 years, soft-deleted records 1 year **[placeholder]** | Proposed | T-082 |

**Rule:** change a status here (with the date and approver) in the same PR that relies on it.

---

## 4. Product Requirements Summary

The full functional requirements (FR-xxx) are in `PDR.md` Section 6. Priorities for the first release:

| Release | Contents |
|---|---|
| **MVP (R1)** | Auth and RBAC, institutions and programs, persons and enrolments, mock APAAR, validation (format, registry, same and cross-institution duplicates), bulk upload, flags, audit log |
| **R2** | Intake, supernumerary, category and date rules, rules config, submission, analytics, live feed |
| **R3** | Signed records, consent, verification (all tiers), public verify page, student view |
| **R4** | ML anomaly detection, reports, certificates, hardening, pilot readiness |

---

## 5. Task Backlog

Status legend: ☐ Todo, ◐ In progress, ☑ Done. Size: **S** (under half a day), **M** (about one day), **L** (up to two days). Split anything larger.

### Phase 0: Foundation

**T-001 Backend skeleton and health endpoint** [S] ◐
- Goal: runnable FastAPI app with typed settings.
- Acceptance:
  - AC1: `GET /api/v1/health` returns `200 {"status":"ok"}`.
  - AC2: Settings load from environment; startup fails with a clear message if a required variable is missing.
  - AC3: OpenAPI docs are served at `/docs` in development only.
- Tests: U settings validation; I health endpoint.

**T-002 Docker Compose for dev services** [S] ☐ Depends: T-001
- Goal: one command starts backend, PostgreSQL and Redis.
- Acceptance:
  - AC1: `docker compose up` brings up all services healthy.
  - AC2: `.env.example` lists every variable with placeholders only.
  - AC3: `.env` is Git-ignored and not present in the repo.
- Tests: manual smoke check recorded in PR.

**T-003 Database session and Alembic baseline** [S] ☐ Depends: T-002 · Blocked by D-01
- Acceptance:
  - AC1: `alembic upgrade head` runs on an empty database.
  - AC2: A DB session dependency is available and closed per request.
  - AC3: Application DB role has no superuser rights.
- Tests: I migration up and down.

**T-004 Backend CI workflow** [S] ☐ Depends: T-001
- Acceptance:
  - AC1: `backend-ci.yml` runs lint, type check and `pytest` on every PR.
  - AC2: The build fails when coverage on `core` is below 80% (once `core` has code).
  - AC3: Dependency vulnerability scan step present.
- Tests: CI run on a sample PR.

**T-005 Frontend skeleton and CI** [S] ☐
- Acceptance:
  - AC1: Vite app builds and shows a placeholder page.
  - AC2: `frontend-ci.yml` runs lint, `tsc` and tests.
  - AC3: Tailwind and the UI component base are configured.
- Tests: U one component test.

**T-006 Error envelope and request IDs** [S] ☐ Depends: T-001
- Acceptance:
  - AC1: Every error returns `{"error":{"code","message","details","request_id"}}`.
  - AC2: Every response includes an `X-Request-ID` header, also present in logs.
  - AC3: Unhandled exceptions return a generic 500 without stack traces or internals.
- Tests: U handler tests; S assert no stack trace or SQL in 500 responses.

### Phase 1: Identity and Access

**T-010 User model and password hashing** [M] ☐ Depends: T-003 · Blocked by D-06
- Acceptance:
  - AC1: `users` table with role enum and institution or person link per Section 2.1.
  - AC2: Passwords stored only as Argon2id hashes; plaintext never logged.
  - AC3: Password policy enforced (minimum length 12, not in a small common-password list).
- Tests: U hashing and policy; S verify no plaintext in DB or logs.

**T-011 Login and access tokens** [M] ☐ Depends: T-010 · Blocked by D-10
- Acceptance:
  - AC1: `POST /auth/login` returns an access token (15 min) and sets the refresh cookie.
  - AC2: Wrong password and unknown email return the same response and similar timing.
  - AC3: `GET /auth/me` returns the current user.
  - AC4: Expired or tampered tokens return 401.
- Tests: U/I login paths; S no user enumeration, tampered and expired token rejection.

**T-012 Refresh rotation and logout** [S] ☐ Depends: T-011
- Acceptance:
  - AC1: Each refresh issues a new refresh token and invalidates the old one.
  - AC2: Reusing an old refresh token revokes the whole token family.
  - AC3: Logout revokes the current refresh token.
- Tests: I rotation; S replay of an old refresh token fails and revokes the family.

**T-013 TOTP two-factor authentication** [M] ☐ Depends: T-011
- Acceptance:
  - AC1: User can enrol (secret and QR), verify a code, and receive backup codes (shown once, stored hashed).
  - AC2: Regulator roles cannot obtain a full session without 2FA.
  - AC3: TOTP secret is stored encrypted.
- Tests: U code verification with time window; S backup code single use, 2FA cannot be bypassed on regulator routes.

**T-014 RBAC dependencies and test matrix** [M] ☐ Depends: T-011
- Acceptance:
  - AC1: `require_role(...)` and `require_permission(...)` dependencies exist and are used by every non-public route.
  - AC2: A test enumerates all registered routes and fails if any non-public route lacks an authorisation dependency.
  - AC3: Institution scoping helper restricts queries to the user's own institution.
- Tests: S route-coverage test, role matrix per Section 4.1 of the PDR, cross-institution access returns 404 or 403.

**T-015 Rate limiting and lockout** [S] ☐ Depends: T-011, T-002
- Acceptance:
  - AC1: Login limited per IP and per account; exceeding returns 429 with `Retry-After`.
  - AC2: Account locks after 5 failed attempts for 15 minutes (configurable).
  - AC3: Lockout and rate-limit events are recorded (T-016 once available).
- Tests: I limits; S lockout cannot be bypassed by changing the case of the email.

**T-016 Audit log service** [M] ☐ Depends: T-003
- Acceptance:
  - AC1: `audit_log` table is append-only for the application DB role (no UPDATE or DELETE grants).
  - AC2: Each entry stores actor, role, action, target, outcome, IP, metadata and `prev_hash` / `entry_hash`.
  - AC3: A verification function detects any altered or removed entry.
  - AC4: Login success and failure, and lockouts, are logged.
- Tests: U hash chain; S attempted UPDATE or DELETE by the app role fails; tamper detection.

**F-001 Login page, auth context and route guards** [M] ☐ Depends: T-011, T-005
- Acceptance:
  - AC1: User logs in, sees role-appropriate home.
  - AC2: Protected routes redirect unauthenticated users; forbidden routes show a 403 page.
  - AC3: Access token is held in memory only; no tokens in `localStorage`.
- Tests: U guard tests; S check no token in browser storage.

### Phase 2: Core Data

**T-020 Institutions, programs, intake allocations** [M] ☐ Depends: T-014
- Acceptance:
  - AC1: Tables and CRUD endpoints for institutions, programs and per-year `intake_allocations`.
  - AC2: Regulator roles manage all; institution users read their own only.
  - AC3: Institution `code` is unique.
- Tests: I CRUD; S institution user cannot read or edit another institution.

**T-021 Field encryption utility** [M] ☐ Depends: T-001
- Acceptance:
  - AC1: AES-256-GCM encrypt and decrypt with a unique nonce per value and a key ID prefix.
  - AC2: Decryption fails on modified ciphertext, wrong key or wrong associated data.
  - AC3: Keyed hash helper (HMAC-SHA256 with pepper) for lookups.
  - AC4: Two encryptions of the same value produce different ciphertext.
- Tests: U roundtrip, tamper, wrong key, nonce uniqueness; S key is never logged.

**T-022 Persons and enrolments schema** [L] ☐ Depends: T-020, T-021 · Blocked by D-01, D-04
- Acceptance:
  - AC1: Migration creates `persons`, `enrolments`, `enrolment_status_history` as in Section 2.1.
  - AC2: Unique index on `persons.apaar_id_hash` (where not null) and the enrolment unique partial index exist.
  - AC3: Inserting the same person into two institutions succeeds; inserting a duplicate exact enrolment fails.
  - AC4: Sensitive columns are encrypted; no plaintext personal data column exists.
- Tests: I constraint behaviour including cross-institution case; S direct SQL inspection shows ciphertext only.

**T-023 Person and enrolment create or edit API** [L] ☐ Depends: T-022, T-016
- Acceptance:
  - AC1: `POST /students` creates or reuses the person (by `apaar_id_hash`) and creates an enrolment for the user's institution.
  - AC2: `PATCH` and soft `DELETE` work only on the user's institution's enrolments.
  - AC3: Responses mask the APAAR ID and personal fields by default.
  - AC4: Create, update and delete are audit logged.
- Tests: I create new person, reuse existing person from another institution; S cross-institution edit blocked, masked output, audit entry present.

**T-024 Masking utility and reveal permission** [S] ☐ Depends: T-021
- Acceptance:
  - AC1: Masking helpers for APAAR, phone, email and name.
  - AC2: Full-value reveal needs a specific permission, and each reveal is audit logged.
  - AC3: Logs and error messages never contain unmasked personal data.
- Tests: U masking; S log scan test for planted sentinel values.

**T-025 Enrolment status history** [S] ☐ Depends: T-023
- Acceptance:
  - AC1: Every status change appends a history row with actor and reason.
  - AC2: Invalid transitions (for example `graduated` to `enrolled`) are rejected.
- Tests: U transition table; I history rows.

**F-002 Institution student pages** [L] ☐ Depends: T-023, F-001
- Acceptance:
  - AC1: Student list (paginated, searchable on non-encrypted fields), add student form with inline validation.
  - AC2: Flag badges use text and icon, not colour alone.
  - AC3: Sensitive values shown masked.
- Tests: U components; E add student flow.

### Phase 3: Mock APAAR and Validation (R1)

**T-030 Mock APAAR service** [M] ☐
- Acceptance:
  - AC1: `GET /lookup/{apaar_id}` returns a record or 404; `GET /health` works.
  - AC2: `generate_data.py` produces seeded, reproducible data including inactive IDs, name mismatches and cross-institution duplicates.
  - AC3: Generated data is clearly synthetic and contains no real personal data.
- Tests: U generator determinism; I lookup.

**T-031 APAAR client adapter** [M] ☐ Depends: T-030
- Acceptance:
  - AC1: `ApaarClient` interface with mock and real implementations (real is a stub raising `NotImplemented`).
  - AC2: Mode chosen by `APAAR_MODE`.
  - AC3: Timeout, limited retries and short-lived cache; on registry failure return an `unavailable` result, not an exception.
- Tests: U/I timeout, retry, cache, unavailable path.

**T-032 Validation engine core** [M] ☐ Depends: T-022
- Acceptance:
  - AC1: `BaseRule`, `RuleContext`, `Flag` and `ValidationEngine` implemented.
  - AC2: Engine loads enabled rules and parameters from `rules_config`; a disabled rule does not run.
  - AC3: A critical `APAAR_FORMAT` flag skips expensive rules for that record.
  - AC4: Each flag stores `rule_code`, `rule_version`, severity, message and details.
- Tests: U engine ordering, disabling, skip policy.

**T-033 Rule APAAR_FORMAT** [S] ☐ Depends: T-032 · Blocked by D-02
- Acceptance:
  - AC1: Valid IDs pass; wrong length, letters, spaces and empty values raise a critical flag.
  - AC2: Pattern comes from configuration.
- Tests: U table-driven cases including boundary lengths and Unicode digits.

**T-034 Rule APAAR_REGISTRY** [M] ☐ Depends: T-031, T-032
- Acceptance:
  - AC1: Unknown ID gives an error flag; inactive ID gives an error flag; matching ID sets `identity_status = verified`.
  - AC2: Name or date of birth mismatch gives a warning without revealing the registry's values in the message.
  - AC3: Registry unavailable gives `identity_status = unverified` and a warning (Clarification C-4).
- Tests: U/I for each path; S flag messages contain no registry personal data.

**T-035 Rule DUP_SAME_INST** [M] ☐ Depends: T-032, T-022
- Acceptance:
  - AC1: Overlapping active enrolments for one person in one institution flag as defined in Section 2.1 (error for same program, warning otherwise).
  - AC2: Non-overlapping periods and soft-deleted enrolments do not flag.
- Tests: U/I overlap boundary cases (touching dates, open end date).

**T-036 Rule DUP_CROSS_INST** [M] ☐ Depends: T-032, T-022 · Blocked by D-12
- Acceptance:
  - AC1: Overlapping `enrolled` enrolments across institutions raise a critical flag on both enrolments.
  - AC2: Overlap within `overlap_grace_days` after a `transferred` status does not flag.
  - AC3: The flag shown to institution A does **not** disclose institution B's identity or student details (only that a conflict exists). The regulator sees both.
- Tests: U/I cases; S institution A cannot learn B's details from the flag or API.

**T-037 Flags API and lifecycle** [M] ☐ Depends: T-032, T-014
- Acceptance:
  - AC1: List, filter and update flags. States: open, acknowledged, resolved, escalated.
  - AC2: Resolution requires a comment and records who and when.
  - AC3: Institution users can act only on their own flags; critical cross-institution flags can be resolved only by a regulator.
- Tests: I lifecycle; S scoping and permission checks.

**T-038 Rule DUP_FUZZY** [L] ☐ Depends: T-032 · Blocked by D-01
- Acceptance:
  - AC1: Similarity uses `name_search_key` plus date of birth plus a secondary attribute; threshold configurable.
  - AC2: Result is a warning that links the two person records (visible only to the regulator).
  - AC3: Test dataset reaches at least 85% recall at the default threshold with no more than 10% false positives.
- Tests: U scoring; I recall and precision on seeded data.

**F-004 Flags page** [M] ☐ Depends: T-037, F-001
- Acceptance: list and filter flags, view details, acknowledge and resolve with comment.
- Tests: U; E resolve flow.

### Phase 4: Bulk Upload (R1)

**T-040 CSV parser and schema** [M] ☐
- Acceptance:
  - AC1: Required columns, types and a maximum row count are enforced; clear row-level errors with row numbers.
  - AC2: Cells starting with `=`, `+`, `-`, `@` are neutralised on export (CSV formula injection).
  - AC3: Encoding problems and BOM are handled.
- Tests: U with sample files; S formula injection payloads.

**T-041 Upload batch API** [M] ☐ Depends: T-040, T-014, T-016
- Acceptance:
  - AC1: `POST /uploads` accepts only CSV within a size limit; checks MIME type and content, not just extension.
  - AC2: Creates `upload_batch` (queued) and returns its ID; an idempotency key prevents double processing.
  - AC3: Institution users see only their own batches.
- Tests: I; S oversized and non-CSV files rejected, cross-institution access blocked.

**T-042 Bulk processing task** [L] ☐ Depends: T-041, T-032 · Blocked by D-03
- Acceptance:
  - AC1: Rows are processed in chunks in a worker; progress is updated on the batch.
  - AC2: A failing row does not stop the batch; valid rows are stored, invalid rows get row-level errors.
  - AC3: 10,000 rows complete in under 2 minutes against the mock registry.
  - AC4: Re-running the same batch (same file hash and key) does not create duplicates.
- Tests: I chunking, partial failure, idempotency; performance test on 10,000 rows.

**T-043 Error report download** [S] ☐ Depends: T-042
- Acceptance: downloadable CSV with row number, field, rule code and message; no personal data beyond the user's own upload.
- Tests: I; S another institution cannot download it.

**T-044 Sample data files** [S] ☐ Depends: T-040
- Acceptance: `students_valid.csv`, `students_with_errors.csv` and `students_duplicates.csv` exist, are synthetic, and each produces the documented result when uploaded.
- Tests: I uploading each file gives the expected counts.

**F-003 Bulk upload UI** [M] ☐ Depends: T-041, T-043, F-001
- Acceptance: drag and drop, progress, summary, sortable error table, download.
- Tests: U; E upload sample file.

### Phase 5: Compliance Rules and Submission (R2)

**T-050 Rule INTAKE_EXCEEDED** [M] ☐ Depends: T-032, T-020 · Blocked by D-09
- Acceptance:
  - AC1: Count of enrolments per program and year is compared with approved intake plus allowed supernumerary seats.
  - AC2: Exact boundary (count equals limit) passes; one over flags.
  - AC3: Bulk mode counts incrementally in memory and gives the same result as one-by-one entry.
- Tests: U boundaries; I bulk versus single parity.

**T-051 Rule SUPERNUMERARY** [S] ☐ Depends: T-050 · Blocked by D-09
- Acceptance: flags excess supernumerary admissions and ineligible categories as configured.
- Tests: U.

**T-052 Rule CATEGORY_CONSISTENCY** [S] ☐ Depends: T-032 · Blocked by D-09
- Acceptance: invalid category and quota combinations flag as a warning, driven by a config table.
- Tests: U table-driven.

**T-053 Rule DATE_CHECKS** [S] ☐ Depends: T-032
- Acceptance: future admission date, implausible age, date outside academic year and end before start flag as errors.
- Tests: U boundary dates.

**T-054 Rules configuration API** [M] ☐ Depends: T-032, T-014, T-016
- Acceptance:
  - AC1: Only `regulator_admin` can read and change rule settings.
  - AC2: Every change creates a new rule version and an audit entry.
  - AC3: Existing flags keep their original `rule_version`.
- Tests: I; S officers and institutions get 403.

**T-055 Submission workflow** [M] ☐ Depends: T-037, T-050
- Acceptance:
  - AC1: Submission is rejected while blocking flags (error or critical) exist.
  - AC2: Successful submission locks the dataset for that year; edits are rejected.
  - AC3: Reopen needs a regulator and is audit logged.
- Tests: I; S institution cannot reopen or bypass the lock.

**F-005 Submission page** [S] · **F-008 Rules config page** [M] ☐

### Phase 6: Analytics and Live Feed (R2)

**T-060 Analytics endpoints** [L] ☐ Depends: T-050
- Acceptance: overview, intake utilisation, state-wise, trend and risk endpoints return aggregated, non-personal data only; response time under 500 ms on the seeded dataset.
- Tests: I; S institution users get 403 on cross-institution analytics; no personal data in responses.

**T-061 WebSocket live feed** [M] ☐ Depends: T-014
- Acceptance:
  - AC1: Authenticated connection only; token checked on connect and on expiry.
  - AC2: Events are filtered by role and institution scope.
  - AC3: Client reconnects after a drop.
- Tests: I; S unauthenticated and out-of-scope subscriptions refused.

**F-006 Regulator dashboard** [L] · **F-009 Audit log page** [S] ☐

### Phase 7: Verification, Consent and Records (R3)

**T-070 Key generation and signing module** [M] ☐ Depends: T-021 · Blocked by D-05
- Acceptance:
  - AC1: `generate_keys.sh` creates an Ed25519 key pair; the private key is never committed and `keys/` is Git-ignored.
  - AC2: Canonical JSON serialisation is deterministic (sorted keys, fixed encoding).
  - AC3: Verify fails for any modified payload, modified signature or wrong key.
  - AC4: `key_id` supports verification with older public keys after rotation.
- Tests: U sign and verify, tamper, rotation; S private key not in logs or API output.

**T-071 Consent model and service** [M] ☐ Depends: T-022, T-016 · Blocked by D-07
- Acceptance:
  - AC1: States: requested, granted, denied, revoked, expired. Allowed transitions only.
  - AC2: Consent has purpose, scope, `expires_at` (default 30 days, maximum 365).
  - AC3: `assert_active(person, verifier, scope)` returns false for revoked, expired, denied or out-of-scope requests.
  - AC4: A background job marks expired consents.
- Tests: U transitions and `assert_active` matrix; S no code path that releases personal data skips `assert_active` (route-level test).

**T-072 Consent API** [M] ☐ Depends: T-071, T-014
- Acceptance:
  - AC1: Verifier creates a request; only the target student can grant or deny; the student can narrow the scope.
  - AC2: Student can revoke at any time; the effect is immediate.
  - AC3: All events are audit logged.
- Tests: I flow; S a verifier cannot approve their own request, a student cannot decide another person's request.

**T-073 Record issue and revoke** [M] ☐ Depends: T-070, T-071 · Blocked by D-05
- Acceptance:
  - AC1: A record is issued only from a granted consent (`consent_id` not null).
  - AC2: Payload contains only consented claims; APAAR ID is masked unless in scope.
  - AC3: Revoking consent revokes its records immediately.
  - AC4: Public token has at least 128 bits of entropy and an expiry.
- Tests: I; S issue without consent impossible, payload minimisation, revocation propagation.

**T-074 Public record verification endpoint** [M] ☐ Depends: T-073
- Acceptance:
  - AC1: Accepts only the token; there is no APAAR ID parameter.
  - AC2: Returns `valid`, `expired` or `revoked` with the signed claims; unknown and malformed tokens return an identical generic response.
  - AC3: Rate limited per IP; each call audit logged with a hashed token reference.
  - AC4: Signature is re-verified on every call.
- Tests: I; S token enumeration and timing differences, rate limiting, tampered stored payload is detected.

**T-075 Verifier lookup (non-disclosing)** [S] ☐ Depends: T-072 · Blocked by D-05, D-11
- Acceptance:
  - AC1: For a verifier, the response is identical for existing and non-existing APAAR IDs (`consent_required`).
  - AC2: Regulator lookups are allowed within role, logged with the stated reason.
  - AC3: Rate limited to prevent enumeration.
- Tests: I; S response bodies, status codes and timing equivalence for existing versus non-existing IDs.

**T-076 Student account activation and self-share** [L] ☐ Depends: T-073 · Blocked by D-08
- Acceptance:
  - AC1: A student activates an account through the agreed onboarding method (D-08) and can see only their own data.
  - AC2: A student can create a self-share (scope, purpose, expiry), producing a record and QR.
  - AC3: Student can list and revoke all active shares and consents.
- Tests: I; S student A cannot view or revoke student B's data.

**F-010 Verifier pages** [M] · **F-011 Student My Record** [L] · **F-012 Public Verify page** [M] ☐ Depends: T-072, T-074, T-076
- Acceptance (F-012): shows an unmistakable VALID, EXPIRED, REVOKED or NOT FOUND state, shows no data beyond the signed claims, and does not store the token in browser history longer than necessary.
- Tests: U; E share to verify flow.

### Phase 8: ML, Reports and Hardening (R4)

**T-062 Feature extraction** [M] ☐ Depends: T-060 · **T-063 Train and score anomaly model** [L] ☐ Depends: T-062 · **T-064 Anomaly review API and UI** [M] ☐ Depends: T-063
- Acceptance (T-063): model and version stored; scores are reproducible for a fixed seed; the top contributing features are returned; no automatic action is taken on a score (Clarification C-3).
- Acceptance (T-064): reviewers can mark confirmed, false positive or needs inspection; decisions are audit logged.
- Tests: U feature calculations; I scoring on seeded anomalies; S only regulator roles can view.

**T-080 Reports** [L] ☐ Depends: T-060 · **T-081 Certificate with QR** [M] ☐ Depends: T-073
- Acceptance: PDF and CSV exports are scoped to the user's authority; exports sanitise formula injection; certificate QR resolves to the T-074 endpoint.

**T-082 Security hardening pass** [L] ☐ Depends: all R1 to R3 tasks · Blocked by D-13
- Acceptance:
  - AC1: Security test catalogue (Section 6) fully automated and green.
  - AC2: Security headers and CORS reviewed; secrets scan clean.
  - AC3: Retention jobs implemented per D-13.
  - AC4: Dependency audit shows no unaddressed high-severity issues.

**T-083 Documentation and demo script** [M] ☐
- Acceptance: `docs/` files completed and consistent with the implemented behaviour; `demo-script.md` can be followed by someone new without help.

---

## 6. Security Test Catalogue

Each item must exist as an automated test. A feature is not Done if its relevant tests are missing.

| ID | Test | Covers |
|---|---|---|
| S-01 | Every non-public route has an authorisation dependency (route enumeration) | T-014 |
| S-02 | Role matrix: each role calling each endpoint group returns the expected status | T-014 |
| S-03 | Institution A cannot read, edit, upload for or download from Institution B | T-020, T-023, T-041, T-043 |
| S-04 | Login does not reveal whether an email exists (response and timing) | T-011 |
| S-05 | Tampered, expired and wrong-key JWTs are rejected | T-011 |
| S-06 | Refresh token replay revokes the token family | T-012 |
| S-07 | Regulator routes cannot be used without completed 2FA | T-013 |
| S-08 | Rate limits and lockout cannot be bypassed by case changes or header spoofing | T-015 |
| S-09 | The application DB role cannot update or delete audit rows; tampering is detected | T-016 |
| S-10 | Database holds only ciphertext for personal fields; tampered ciphertext fails to decrypt | T-021, T-022 |
| S-11 | Sentinel personal values never appear in logs or error bodies | T-006, T-024 |
| S-12 | Full-value reveal needs permission and creates an audit entry | T-024 |
| S-13 | Cross-institution flags do not disclose the other institution's details | T-036 |
| S-14 | CSV upload: oversized, wrong type and formula-injection files are handled safely | T-040, T-041 |
| S-15 | Only `regulator_admin` can change rules; changes are versioned and audited | T-054 |
| S-16 | A locked submission cannot be edited by an institution | T-055 |
| S-17 | WebSocket refuses unauthenticated and out-of-scope subscriptions | T-061 |
| S-18 | Signature verification fails for any changed payload, signature or key | T-070 |
| S-19 | No personal-data-releasing path skips the consent check | T-071 |
| S-20 | Users cannot approve their own consent request or decide another person's | T-072 |
| S-21 | A record cannot be issued without a granted consent | T-073 |
| S-22 | Revoking consent makes the record show `revoked` immediately | T-073, T-074 |
| S-23 | Public endpoint: unknown, malformed and expired tokens give indistinguishable generic results; rate limited | T-074 |
| S-24 | Verifier lookup is identical for existing and non-existing APAAR IDs | T-075 |
| S-25 | Student A cannot see or revoke Student B's data, consents or shares | T-076 |
| S-26 | Anomaly scores cause no automatic data changes | T-063 |

---

## 7. Suggested Order of Work

```
R1 (MVP):  T-001..T-006 -> T-010..T-016, F-001 -> T-020..T-025, F-002
           -> T-030..T-037, F-004 -> T-038 -> T-040..T-044, F-003
R2:        T-050..T-055, F-005, F-008 -> T-060, T-061, F-006, F-009
R3:        T-070 -> T-071 -> T-072 -> T-073 -> T-074 -> T-075 -> T-076, F-010..F-012
R4:        T-062..T-064 -> T-080, T-081 -> T-082 -> T-083
```

**Before R1 starts:** confirm D-01, D-02, D-03, D-04, D-06, D-10.
**Before R3 starts:** confirm D-05, D-07, D-08, D-11 and complete the legal review of consent and retention.

---

## 8. Change Log

| Version | Date | Change |
|---|---|---|
| 0.1 | 28 Oct 2026 | Initial PRD created from design review. Introduced the person and enrolment split (ID-1) and the tiered disclosure model (VER-1). |
