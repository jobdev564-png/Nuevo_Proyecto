# Tasks: 002-task-lifecycle-recovery

**Input**: Design documents from `/specs/002-task-lifecycle-recovery/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included — test-first (Red-Green-Refactor) is MANDATORY per constitution Principle IV and plan.md §7. Write each story's tests first, verify they FAIL, then implement.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1 = HU-05, US2 = HU-06, US3 = HU-14)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify Increment 1 baseline and tooling before any change

- [X] T001 Verify Increment 1 baseline green (run pytest in tests/services/test_task_service.py and tests/functional/test_task_routes.py) with no code changes
- [X] T002 [P] Verify test and migration tooling (pytest, pytest-flask, Flask-Migrate/Alembic) declared in requirements.txt
- [X] T003 [P] Verify env and run entrypoints (.env with SECRET_KEY/DATABASE_URL, run.ps1 / flask run) per quickstart.md §1 in run.ps1

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared schema migration and domain conventions that MUST complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Create Alembic migration add_soft_delete_and_reset_tokens in migrations/versions/ (ADD COLUMN tasks.is_deleted BOOLEAN NOT NULL SERVER_DEFAULT '0' + INDEX ix_tasks_is_deleted, ADD COLUMN tasks.deleted_at DATETIME NULL, CREATE TABLE password_reset_tokens with FK user_id→users.id ON DELETE CASCADE + INDEX(user_id) + UNIQUE(token_hash), reversible downgrade)
- [X] T005 Apply and verify migration on dev/test databases via flask db upgrade in migrations/versions/ (existing Increment 1 rows backfill is_deleted=False/deleted_at=NULL with no manual UPDATE)
- [X] T006 Add shared delete-state exceptions TaskAlreadyDeletedError and TaskDeletedError in src/taskcontrol/services/task_service.py (alongside existing TaskNotFoundError/InvalidStateTransitionError)
- [X] T007 Document audit vocabulary TASK_DELETED, TASK_REOPENED, PASSWORD_RESET_REQUESTED, PASSWORD_RESET_COMPLETED (4 mandatory fields actor_id/action/entity_id/timestamp, details without secrets) in src/taskcontrol/services/audit_service.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Eliminación lógica de tareas HU-05 (Priority: P1) 🎯 MVP

**Goal**: Authenticated user soft-deletes own task; it disappears from default listing, physical row + audit history preserved, second delete rejected, edit/status on deleted blocked.

**Independent Test**: Create task → POST delete → GET /tasks excludes it while DB row persists with is_deleted=True/deleted_at set and AuditLog TASK_DELETED with actor_id/action/entity_id/timestamp; second delete → 404 TASK_ALREADY_DELETED with no new audit (spec.md US1 + SC-001/SC-002).

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (Principle IV, research.md R-06)**

- [X] T008 [P] [US1] Service tests for soft-delete (list exclusion, double-delete rejection, edit/status/reopen-on-deleted blocked, TASK_DELETED 4 fields) in tests/services/test_task_soft_delete.py
- [X] T009 [P] [US1] Route tests for POST /tasks/<id>/delete (200/302 success, 404 TASK_NOT_FOUND/TASK_ALREADY_DELETED, 401 no session, cross-user 403/404) in tests/functional/test_task_lifecycle_routes.py

### Implementation for User Story 1

- [X] T010 [P] [US1] Extend Task model with is_deleted Boolean "NOT NULL, DEFAULT False, INDEX" and deleted_at DateTime "NULLABLE, UTC" in src/taskcontrol/models/task.py
- [X] T011 [US1] Implement TaskService.delete_task plus harden get_user_tasks (WHERE is_deleted=FALSE before status filter) and get_task_by_id/update paths in src/taskcontrol/services/task_service.py (depends on T010; create always is_deleted=False/deleted_at=None; second delete raises without new audit; never call db.session.delete(task))
- [X] T012 [US1] Implement POST /tasks/<int:task_id>/delete canonical (plus optional DELETE /tasks/<int:task_id> alias, same semantics) with login_required in src/taskcontrol/routes/tasks.py (depends on T011; 200 {id, is_deleted:true, deleted_at} / 302→/tasks; 404 TASK_NOT_FOUND/TASK_ALREADY_DELETED; 401)
- [X] T013 [P] [US1] Add Eliminar button and flash/302 handling plus exclusion of deleted from list rendering in src/taskcontrol/templates/tasks/index.html
- [X] T014 [US1] Enforce deleted-task guards on edit/status/direct-read (404 TASK_NOT_FOUND or 400 TASK_DELETED per contracts transversal guard) in src/taskcontrol/routes/tasks.py and src/taskcontrol/services/task_service.py (depends on T011)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 3 - Recuperación segura de contraseña HU-14 (Priority: P1)

**Goal**: Public password-reset request with identical neutral response for existing/non-existing emails, crypto-secure single-use 60-min tokens with rotation, hash-only storage, prior-session invalidation.

**Independent Test**: Request with existing vs. non-existing email → identical 200 neutral message; use received token to set new password → login works; reuse/expired/manipulated token → 400 INVALID_OR_EXPIRED_TOKEN; new request invalidates prior tokens; audit PASSWORD_RESET_REQUESTED/COMPLETED with no secrets (spec.md US3 + SC-004/SC-005/SC-006).

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T015 [P] [US3] Service tests for reset (neutral response, valid-token rotation, reuse/expiry rejection, rotation invalidates priors, password rule ≥8 identical to registration) in tests/services/test_password_reset_service.py
- [X] T016 [P] [US3] Route tests for POST /auth/password-reset-request and POST /auth/password-reset-confirm (200 neutral, 400 VALIDATION_ERROR/INVALID_OR_EXPIRED_TOKEN, never 404/409 on request) in tests/functional/test_password_reset_routes.py

### Implementation for User Story 3

- [X] T017 [P] [US3] Create PasswordResetToken model with user_id Integer "FK users.id ON DELETE CASCADE, NOT NULL, INDEX", token_hash String(255) "NOT NULL, UNIQUE, INDEX — SHA256 hex", expires_at DateTime "NOT NULL, UTC — created_at + 60 min", used_at DateTime "NULLABLE, UTC — NULL=vivo", created_at DateTime "NOT NULL, UTC, DEFAULT now" in src/taskcontrol/models/password_reset_token.py and export it in src/taskcontrol/models/__init__.py
- [X] T018 [US3] Implement PasswordResetService.request_reset and confirm_reset with rotation (new token marks prior live used_at=now), atomic consumption (password_hash update + used_at=now + PASSWORD_RESET_COMPLETED), SHA-256 lookup, dev log-simulated mail link, testing-only get_last_token_for_email hook in src/taskcontrol/services/password_reset_service.py (depends on T017; persist only token_hash; normalize email strip().lower(); never audit non-existing emails with PII; details always secret-free; new_password rule "mínimo 8 caracteres, no vacía" identical to UserService.register_user)
- [X] T019 [US3] Implement POST /auth/password-reset-request (public, 200 neutral message identical both branches, 400 only when email field missing) and POST /auth/password-reset-confirm (public, token-as-credential, 200 {email} / 400 INVALID_OR_EXPIRED_TOKEN / 400 VALIDATION_ERROR) in src/taskcontrol/routes/auth.py (depends on T018; malformed tokens → INVALID_OR_EXPIRED_TOKEN never 500; never log token/new_password)
- [X] T020 [P] [US3] Add reset request/confirm forms with neutral confirmation rendering in src/taskcontrol/templates/auth/login.html and src/taskcontrol/templates/auth/register.html (new password-reset templates alongside if preferred)
- [X] T021 [US3] Invalidate/rotate prior web sessions after successful reset in src/taskcontrol/routes/auth.py (depends on T019)

**Checkpoint**: At this point, User Stories 1 AND 3 should both work independently

---

## Phase 5: User Story 2 - Reapertura de tareas completadas HU-06 (Priority: P2)

**Goal**: Dedicated reopen completed→pending with explicit TASK_REOPENED audit distinguishable from STATUS_CHANGED; non-completed/deleted/cross-user attempts rejected; update_task_status completed→* stays blocked.

**Independent Test**: Complete own task → POST reopen → status pending, reappears in ?status=pending, audit TASK_REOPENED with previous_status/completed→current_status/pending; reopen on pending/in_progress/deleted → 400/404; cross-user → 403/404; POST /status pending from completed → still 400 (spec.md US2 + SC-003).

**Story dependency**: Requires US1 soft-delete guards (is_deleted checks) — implement US1 first, then US2.

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T022 [P] [US2] Service tests for reopen (completed→pending + TASK_REOPENED, pending/in_progress/deleted rejection, update_task_status completed→pending still 400, concurrency second-request 400 without duplicate event) in tests/services/test_task_reopen.py
- [X] T023 [P] [US2] Route tests for POST /tasks/<id>/reopen (200 {previous_status, current_status}, 400 INVALID_STATE_TRANSITION, 404 TASK_NOT_FOUND, 401) in tests/functional/test_task_lifecycle_routes.py

### Implementation for User Story 2

- [X] T024 [US2] Implement TaskService.reopen_task (only legal completed→pending; require is_deleted=False, status=='completed', ownership; emit TASK_REOPENED with details {previous_status:'completed', current_status:'pending'}) in src/taskcontrol/services/task_service.py (depends on Phase 3 US1 guards; keep VALID_TRANSITIONS completed→{} empty)
- [X] T025 [US2] Implement POST /tasks/<int:task_id>/reopen with login_required in src/taskcontrol/routes/tasks.py (depends on T024; never reuse /status for reopen)
- [X] T026 [P] [US2] Add Reabrir button and pending-filter reappearance rendering in src/taskcontrol/templates/tasks/index.html

**Checkpoint**: All user stories should now be independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Integrity, security, and E2E validation across stories

- [X] T027 [P] Enforce no-physical-delete guard (grep for db.session.delete(task) must return zero hits in src/) and document the prohibition in src/taskcontrol/services/task_service.py
- [X] T028 [P] Verify zero-plaintext audit (PASSWORD_RESET_REQUESTED/COMPLETED details empty/secret-free, no token_hash/password leakage) across src/taskcontrol/services/password_reset_service.py and src/taskcontrol/services/audit_service.py
- [X] T029 Run quickstart.md E1/E2/E3 E2E validation plus full pytest -v suite in tests/ (all suites green before merge per constitution Quality Gates)
- [X] T030 Review timing-oracle and error-shape neutrality (identical 200 shape/timing on reset-request both branches; no 404/409; generic INVALID_OR_EXPIRED_TOKEN message) in src/taskcontrol/routes/auth.py and src/taskcontrol/services/password_reset_service.py

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3/4/5)**: All depend on Foundational phase completion
  - US1 (HU-05, P1) first — provides is_deleted guards; MVP
  - US3 (HU-14, P1) next — independent model/service except shared migration; can parallelize with US1 after Foundational if staffed
  - US2 (HU-06, P2) last — depends on US1 deleted-guards; do not start before US1 service layer (T011) is done
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 / HU-05 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 3 / HU-14 (P1)**: Can start after Foundational (Phase 2) - Independent of US1 except shared migration; independently testable
- **User Story 2 / HU-06 (P2)**: Depends on US1 (needs is_deleted=False guard + get_task_by_id filtering) - independently testable once US1 service layer exists

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services
- Services before endpoints
- Core implementation before integration (templates/JS)
- Story complete before moving to next priority (except US1/US3 parallelization noted above)

### Parallel Opportunities

- Setup: T002, T003 can run in parallel
- Foundational: T004→T005 sequential (migration then apply); T006, T007 can parallelize with T004
- US1: T008, T009 (tests) in parallel; T010 + T013 in parallel (different files); T011→T012→T014 sequential
- US3: T015, T016 (tests) in parallel; T017 + T020 in parallel; T018→T019→T021 sequential
- US2: T022, T023 (tests) in parallel; T024→T025 sequential; T026 parallel with T024/T025 (different file)
- Polish: T027, T028 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Service tests for soft-delete in tests/services/test_task_soft_delete.py" (T008)
Task: "Route tests for POST /tasks/<id>/delete in tests/functional/test_task_lifecycle_routes.py" (T009)

# Launch model + template for User Story 1 together (different files):
Task: "Extend Task model in src/taskcontrol/models/task.py" (T010)
Task: "Add Eliminar button in src/taskcontrol/templates/tasks/index.html" (T013)
```

## Parallel Example: User Story 3

```bash
# Launch all tests for User Story 3 together:
Task: "Service tests for reset in tests/services/test_password_reset_service.py" (T015)
Task: "Route tests for reset request/confirm in tests/functional/test_password_reset_routes.py" (T016)

# Launch model + template together:
Task: "Create PasswordResetToken model in src/taskcontrol/models/password_reset_token.py" (T017)
Task: "Add reset forms in src/taskcontrol/templates/auth/login.html" (T020)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T007) — CRITICAL, blocks all stories
3. Complete Phase 3: User Story 1 HU-05 (T008-T014)
4. **STOP and VALIDATE**: Independent test per Phase 3 (soft-delete E1 in quickstart.md) + pytest tests/services/test_task_soft_delete.py
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US1 (HU-05, P1) → Test independently → Deploy/Demo (MVP!)
3. Add US3 (HU-14, P1) → Test independently → Deploy/Demo
4. Add US2 (HU-06, P2) → Test independently → Deploy/Demo
5. Each story adds value without breaking previous stories (GET /tasks contract unchanged except deleted exclusion; update_task_status completed→* still 400)

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (HU-05)
   - Developer B: User Story 3 (HU-14)
   - Developer C: joins US2 (HU-06) after Developer A finishes T011
3. Stories complete and integrate independently; final Polish together

---

## Notes

- [P] tasks = different files, no dependencies
- [US1]/[US2]/[US3] labels map to spec.md User Stories 1/2/3 (HU-05/HU-06/HU-14) for traceability
- Each user story is independently completable and testable
- Verify tests fail before implementing (Red-Green-Refactor, Principle IV)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same-file conflicts, cross-story dependencies that break independence (only exception: US2→US1 deleted-guard, documented above)
