# EXAMS module

EXAMS is an assessment module inside MNH Smart Calendar. It is isolated from the legacy calendar `examinations` collection and deliberately keeps all new state in `exams_*` collections plus the append-only `exams_audit_ledger` table.

The server is authoritative: availability, attempts, timing, autosave revisions, submission idempotency, scoring, grade overrides, result release and permissions are all decided in `backend/app/exams/routes.py`. The browser is a presentation client only.

## Storage and isolation

Collections used by EXAMS:

- `exams_exams` — exam definitions, question links, availability window, duration, attempts, randomization and result-release policy.
- `exams_questions` — question bank with answer keys, explanation, rubric, points and active flag.
- `exams_enrollments` — exam-scoped `candidate`, `invigilator` and `grader` capability grants.
- `exams_sessions` — attempts, answers, presentation order, activity events, flags, notes and timing.
- `exams_submissions` — frozen submitted answers, scores, grading state and release metadata.
- `exams_identities` — reserved for future explicit identity mapping; no separate password system is used.
- `exams_audit_events` — reserved mirror name; the live ledger is `exams_audit_ledger`.

The generic `/api/export` and `/api/restore` endpoints still exclude every `exams_*` collection. EXAMS has its own explicit backup/restore surface.

Critical flows (`start`, `autosave`, `submit`, grading and invigilation actions) use `store.exam_transaction()`: a shared write lock plus a SQLite `BEGIN IMMEDIATE` transaction. Session, submission and audit writes therefore commit together or roll back together. Clients also send `expected_updated_at`; a stale revision produces a conflict response instead of overwriting newer work.

## Identity and permissions

EXAMS reuses the existing MNH `mnh_session` cookie through `app.services.authentication`; it does not create a parallel login or password store. Role mapping is:

| MNH role | EXAMS role | Main capabilities |
| --- | --- | --- |
| `administrator` | `exam_admin` | view, manage, question manage, session manage, invigilate, grade, analytics, audit, backup |
| `hod`, `coordinator` | `exam_officer` | view, manage, question manage, session manage, invigilate, analytics, audit, backup |
| `lecturer` | `instructor` | view, manage, question manage, grade, analytics |
| `executive_dean` | `exam_reviewer` | view, analytics, audit |
| no/other session | `guest` | view |

Enrollment records add capabilities for **that exam only**: `candidate` adds take, `invigilator` adds invigilate/audit, and `grader` adds grade/analytics. Global capabilities already allow the same action without an enrollment. Backup and overwrite-conflict powers are admin-only.

A request without a valid `mnh_session` is `public`/`guest`: it can read public exam metadata but cannot start an attempt or manage data. This repository does not add a new browser login endpoint; deployments must supply the existing session cookie from a trusted sign-in flow. Tests create it directly with `authentication.create_session(role)`.

## Exam lifecycle

- Build questions with `POST/PUT/DELETE /api/exams/questions`. Answer keys, explanations and rubrics are returned only to callers with question-management or grading rights.
- Build exams with `POST/PUT/DELETE /api/exams/exams`; `DELETE` archives and preserves historical sessions/submissions.
- Add candidates and staff with `/api/exams/enrollments`. Removing an enrollment during an active attempt flags/audits that attempt instead of erasing it; new starts remain blocked when enrollment is required.
- Publish an exam (`status: "published"`) before candidates can start it. Optional `available_from` and `available_until` bound the window; managers may start outside it.
- `max_attempts` is enforced by the server. `POST /api/exams/sessions/start` resumes the existing active/submitted attempt when present.
- `require_enrollment` blocks unauthenticated or unenrolled candidates unless the caller has `exams.manage`.

## Taking an exam

`GET /api/exams/sessions/{id}` returns the candidate's sanitized questions in the session's stored presentation order. When randomization is enabled, the order is derived deterministically from the session ID; scoring still maps by stable question ID.

`POST /api/exams/sessions/{id}/autosave` accepts `answers`, `client_save_id`, `seq` and `expected_updated_at`. The server:

1. rejects or records stale CAS revisions as conflicts;
2. ignores saves after submit, while paused, or after expiry;
3. de-duplicates repeated `client_save_id` values;
4. sanitizes answers to known questions and valid option IDs before storing them;
5. caps answer keys, values and total payload size.

`POST /api/exams/sessions/{id}/submit` is idempotent by session and `client_submit_id`. Concurrent duplicate submissions return the same submission. A late submit is rejected with HTTP 409, and the expiry event plus audit record are committed before the error is returned. Autosaves received after submission are ignored and never mutate the frozen submission.

The browser shows a server-synced countdown, disables controls when the attempt is not active, saves periodically, and uses custom accessible dialogs. No `confirm()`, `alert()` or `prompt()` is used.

## Grading and result release

Objective types (`mcq`, `multiple_select`, `true_false`) are auto-scored. `short_text` and `essay` answers may be graded per question; exact-text matches are retained as provisional auto-scores for older exams. A grader can override any per-question score and add feedback.

`POST /api/exams/submissions/{id}/grade` uses `expected_updated_at` CAS and stores per-question scores, overall feedback, status (`submitted`, `graded`, `returned`) and release metadata. Conflicts are audited and returned without overwriting the newer grade.

Result visibility is controlled by `results_release`:

- `immediate` — visible as soon as the submission exists;
- `on_return` — visible when status becomes `returned` (default for new exams);
- `scheduled` — visible from `results_release_at`;
- `never` — never exposed to the candidate.

Legacy exams with no stored policy keep the original immediate-release behavior. Candidates never receive answers, scores or feedback before release; graders and managers retain full review access.

## Invigilation (activity signals only)

`GET /api/exams/sessions/monitor` provides an exam-scoped staff roster. `POST /api/exams/sessions/{id}/events` records browser-visible signals (`tab_hidden`, `tab_visible`, `focus_lost`, `focus_gained`, `offline`, `reconnected`, `save_conflict`, `late_submit`), de-duplicated by `client_event_id`. Repeated conflicts and suspicious signals become session flags.

`POST /api/exams/sessions/{id}/actions` supports `extend_time`, `pause`, `resume`, `flag`, `invalidate` and `note`. Each action requires invigilation capability, uses CAS, stores a reason, and writes before/after state summaries to the audit ledger.

This is **activity/event logging, not remote proctoring or device lockdown**. Browser signals can be spoofed and must not be treated as proof of misconduct.

## Analytics

`GET /api/exams/analytics` (and `/analytics/export?format=csv`) is limited to management, grading or analytics roles. It reports per-exam enrolled candidates, attempts, submissions, completion rate, average/median score, pass rate, manual-grading count, hourly submission buckets, and per-question difficulty/discrimination from the high/low thirds. CSV export is audit-logged.

## Audit integrity

Every significant action is appended to `exams_audit_ledger` with actor identity, action, entity IDs, request/client IDs, before/after summaries, a canonical payload and `prev_hash`/`event_hash` SHA-256 links. `GET /api/exams/audit` lists recent events; `GET /api/exams/audit/verify` verifies every hash link.

SQLite additionally installs triggers that abort `UPDATE` and `DELETE` on the ledger. Postgres deployments use the same append-only application contract and hash chain; they do not get the SQLite trigger protection. Manual ledger edits are unsupported.

## Backup and restore

`GET /api/exams/backup` exports all `exams_*` documents with schema version `mnh-exams-backup-v1` and a SHA-256 integrity value. `POST /api/exams/restore` verifies that checksum, validates collections, refuses unknown schema versions, and blocks conflicts unless `overwrite_conflicts` is set by an `exam_admin`.

The export contains answer keys, candidate answers and grades. Store it securely. The append-only audit ledger is intentionally **not** restored by this endpoint; keep normal database snapshots for full disaster recovery.

## Build and verification

After changing EXAMS frontend files, bump the shared build id in:

- `backend/app/config.py` (`BUILD_ID`);
- `frontend/index.html` (`window.MNH_BUILD` and every `?v=` asset marker);
- `frontend/service-worker.js` (`const BUILD`);
- `scripts/build_statistical_glossary.py` (`BUILD`), then regenerate `frontend/resources/python-statistical-tests-glossary.html` and `backend/app/class_rep/data/local_teaching_knowledge.json`;
- hard-coded build assertions in `tests/` and `backend/tests/`;
- the build note in `docs/CHANGELOG-REMEDIATION.md`.

Verification commands:

```powershell
python -m pytest backend/tests/test_exams_foundation.py -q
python -m pytest backend/tests/test_exams_workflows.py -q
python -m py_compile backend/app/exams/routes.py backend/app/exams/schemas.py backend/app/exams/store.py backend/app/exams/permissions.py backend/app/exams/audit.py
node --check frontend/js/exams.js
python -m pytest -q
```

The full suite contains known pre-existing failures outside EXAMS; compare against the clean baseline before treating them as regressions.
