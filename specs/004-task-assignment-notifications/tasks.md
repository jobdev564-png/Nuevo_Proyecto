# Tasks: 004-task-assignment-notifications

**Input**: Design documents from `/specs/004-task-assignment-notifications/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/
**Tests**: Included per constitution Principle IV (test-first bloqueante) and plan §7 blocking suites — write tests FIRST, ensure they FAIL before implementation.
**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1 = HU-10, US2 = HU-11)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Baseline verification before touching schema or services

- [x] T001 Verify baseline increments 1–3 green with `pytest tests/ -q` from repo root (no code changes)
- [x] T002 [P] Review contract decisions in `specs/004-task-assignment-notifications/contracts/assignment-notification-contracts.md` and data-model delta in `specs/004-task-assignment-notifications/data-model.md` before coding

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema + base models that MUST be complete before ANY user story work

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Create Notification model in `src/taskcontrol/models/notification.py` with fields `id` (PK autoincrement), `user_id` (FK `users.id` ON DELETE CASCADE, NOT NULL, INDEX — destinatario), `task_id` (FK `tasks.id` sin cascade, NOT NULL, INDEX), `assigned_by` (FK `users.id` sin cascade, NOT NULL), `created_at` (DateTime NOT NULL UTC DEFAULT now), `is_read` (Boolean NOT NULL DEFAULT `False`), `read_at` (DateTime NULLABLE UTC)
- [x] T004 [P] Extend Task model in `src/taskcontrol/models/task.py` with `created_by` (Integer, FK `users.id` sin cascade de borrado, NOT NULL — creador original inmutable, jamás muta tras creación) plus `creator` relationship coexisting with existing `user_id` backref
- [x] T005 [P] Export Notification in `src/taskcontrol/models/__init__.py` (add to imports and `__all__`)
- [x] T006 [P] Add informative User relationships (`created_tasks`, notifications) lazy without DDL in `src/taskcontrol/models/user.py`
- [x] T007 Generate reversible Alembic migration `add_assignment_and_notifications` in `migrations/versions/` via `flask db migrate` covering `tasks.created_by` (ADD NULL → backfill `created_by = user_id` → SET NOT NULL + FK) and `CREATE TABLE notifications` with INDEX(user_id), INDEX(task_id), INDEX(user_id, is_read, created_at)
- [x] T008 Apply and verify migration with `flask db upgrade` then `flask db downgrade -1 && flask db upgrade` from repo root, confirming pre-existing tasks get `created_by = user_id` and no data loss

**Checkpoint**: Foundation ready — `notifications` table exists, `tasks.created_by` backfilled, user story implementation can now begin

---

## Phase 3: User Story 1 — Asignar tarea propia a otro usuario existente, HU-10 (Priority: P1) 🎯 MVP

**Goal**: Authenticated user assigns own active task to another registered user by email; transfer of single responsibility (`task.user_id` mutates, `created_by` never changes); backend-validated recipient; `TASK_ASSIGNED` audit + exactly one notification in a single transaction; assignee sees task in own list with "Asignada a mí" label and origin filter.

**Independent Test**: Create users A and B; as A create task and `POST /tasks/<id>/assign {"email": "b@..."}` → 200; B lists task with identical title/status/due date and label, A no longer lists it; assign to unregistered email → 404 USER_NOT_FOUND with no mutation, no `TASK_ASSIGNED`, no notification; assign foreign/deleted task → 404; self-assign → 400 ASSIGN_TO_SELF.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (Principio IV)**

- [x] T009 [P] [US1] Service tests for transfer, rejection to nonexistent user, assignee listing, self-assign, foreign/deleted guards, `TASK_ASSIGNED` 4-field audit, and atomicity with injected failure in `tests/services/test_task_assignment_service.py`
- [x] T010 [P] [US1] Functional tests for `POST /tasks/<id>/assign` codes (200/302, 401, 404 TASK_NOT_FOUND, 404 USER_NOT_FOUND, 400 ASSIGN_TO_SELF, 400 VALIDATION_ERROR) and `GET /tasks?origin=all|mine|assigned` compatibility in `tests/functional/test_assignment_routes.py`

### Implementation for User Story 1

- [x] T011 [US1] Add `UserNotFoundError` and `AssignToSelfError` exception classes in `src/taskcontrol/services/task_service.py`
- [x] T012 [US1] Implement `TaskService.assign_task(actor_id, task_id, raw_email)` in `src/taskcontrol/services/task_service.py` (load live owned task → 404 if foreign/deleted; normalize email `strip().lower()` + format check → 400; backend recipient lookup → 404 USER_NOT_FOUND with zero side effects; reject self-assign → 400; single-transaction `task.user_id` transfer + `AuditService.log_event(TASK_ASSIGNED, details={previous_owner_id, new_owner_id, assigned_to_email})` + `Notification(user_id=destino, task_id, assigned_by=actor)` + unique `commit()`)
- [x] T013 [US1] Extend `create_task()` (`user_id = created_by = autor`) and `get_user_tasks()` with `origin` parameter (`mine` ⇔ `created_by == viewer AND user_id == viewer`, `assigned` ⇔ `user_id == viewer AND created_by != viewer`, `all`/absent/invalid ⇔ `user_id == viewer`) in `src/taskcontrol/services/task_service.py`
- [x] T014 [US1] Extend `Task.to_dict()` in `src/taskcontrol/models/task.py` with read-only `created_by` (Integer NOT NULL), `assigned` (Boolean, `created_by != user_id`), `assigned_by_email` without removing existing fields
- [x] T015 [US1] Implement `POST /tasks/<task_id>/assign` (JSON `{email}` + HTML form `email`, auth required, exception→code mapping, 200 `{id, previous_owner_id, new_owner_id, assigned_to_email}` / 302 → `/tasks`) in `src/taskcontrol/routes/tasks.py`
- [x] T016 [US1] Extend `GET /tasks` with `?origin=` query (absent/invalid ≡ `all`, combinable with `status`/ordering, echoes `origin` in JSON envelope) in `src/taskcontrol/routes/tasks.py`
- [x] T017 [US1] Add assign-by-email form plus "Asignada a mí (por …)" label and "Todas / Creadas por mí / Asignadas a mí" filter feeding on `assigned`/`assigned_by_email`/`origin` in `src/taskcontrol/templates/tasks/index.html`

**Checkpoint**: At this point, User Story 1 is fully functional and testable independently (quickstart.md Escenarios A, B, D-parcial)

---

## Phase 4: User Story 2 — Recibir y gestionar notificación interna de asignación, HU-11 (Priority: P2)

**Goal**: Assignee receives in-app notification per successful assignment; pending indicator visible without scanning task list (classic server reload, no async); explicit individual + bulk mark-as-read that persists history in read state; orphaned notifications survive task deletion.

**Independent Test**: Assign A→B, as B `GET /notifications` shows exactly 1 item with task/assignor/date and `unread_count=1`; `POST /notifications/<id>/read` → 200, item persists as read, `unread_count=0`; second assignment + `POST /notifications/read-all` → `marked_count=1`, history keeps both as read; failed assignment creates zero notifications; foreign notification read → 404.

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (Principio IV)**

- [x] T018 [P] [US2] Service tests for one-notification-per-assignment, `unread_count`, idempotent `mark_read`/`mark_all_read` with persistence, recipient isolation, and orphan survival after soft-delete in `tests/services/test_notification_service.py`
- [x] T019 [P] [US2] Functional tests for `GET /notifications` (200 + `unread_count`, 401), `POST /notifications/<id>/read` (200 idempotent, 404 NOTIFICATION_NOT_FOUND), `POST /notifications/read-all` (200 `{marked_count}`, route registered before `/<id>/read`) in `tests/functional/test_notification_routes.py`

### Implementation for User Story 2

- [x] T020 [US2] Implement `NotificationService` (`list_for_user` ordered `created_at DESC` + optional `unread_only`, `mark_read` idempotent `is_read=True, read_at=now_utc`, `mark_all_read` batch returning `marked_count`, `unread_count` as `COUNT WHERE user_id AND is_read = FALSE`, foreign → `NotificationNotFoundError`, never deletes rows) in `src/taskcontrol/services/notification_service.py`
- [x] T021 [US2] Implement notifications blueprint (`GET /notifications` with `?unread_only`, `POST /notifications/<id>/read`, `POST /notifications/read-all`, auth required, JSON envelope `{status, data, code?}` + HTML 302 branches, orphan item keeps `task_title` with unavailable-task navigation note) in `src/taskcontrol/routes/notifications.py`
- [x] T022 [US2] Register `notifications_bp` with `url_prefix="/notifications"` in `src/taskcontrol/__init__.py`
- [x] T023 [US2] Create notifications page with pending indicator, read/unread visual distinction (atenuadas o marca "leída"), task/assignor/date data, and individual + "marcar todas como leídas" actions in `src/taskcontrol/templates/notifications/index.html`
- [x] T024 [US2] Surface `unread_count` indicator without full task-list scan in `src/taskcontrol/templates/base.html` (and task-list link where applicable)

**Checkpoint**: At this point, User Stories 1 AND 2 both work — full delegation cycle A→B→C with persistent read history (quickstart.md Escenarios C, D-completo)

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: E2E validation, quality gates, and constitution compliance

- [x] T025 Run full quickstart validation (Escenarios A–D plus rejection matrix: foreign/deleted → 404, self → 400, malformed → 400, foreign notification → 404, no session → 401, `?origin=bogus` ≡ `all`) per `specs/004-task-assignment-notifications/quickstart.md`
- [x] T026 [P] Run full test suite `pytest tests/ -q` from repo root and confirm zero regressions on prior increments plus byte-compatibility of `GET /tasks` without `origin`
- [x] T027 [P] Verify constitution gates: no blueprint→ORM direct access (Principio II), recipient resolved in service with normalized email (Principio VII), `TASK_ASSIGNED` with `actor_id/action/entity_id/timestamp` UTC ISO-8601 per mutation (Principio VIII), no queues/mail/push, no `db.create_all()` or manual DDL

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - US1 then US2 sequentially (US2 E2E notification flow rides on US1 `assign_task` creation path; US2 service unit tests can be developed in parallel once T003 lands)
  - Or US1/US2 service tests in parallel after Foundational if staffed
- **Polish (Final Phase)**: Depends on US1 + US2 completion

### User Story Dependencies

- **User Story 1 — HU-10 (P1)**: Starts after Foundational — no dependencies on other stories
- **User Story 2 — HU-11 (P2)**: Starts after Foundational — service layer independently testable by seeding `Notification` rows directly, but E2E acceptance (assign → notify → read) requires US1 `assign_task` complete

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services; services before endpoints; endpoints before templates
- T012 (assign_task) before T015/T016 (routes); T020 (NotificationService) before T021 (blueprint)
- T007 migration before T008 upgrade verification; T008 before any service/route task touching new columns

### Parallel Opportunities

- T002 with T001 (review + baseline check touch different concerns)
- T004, T005, T006 model/export tasks in parallel (different files: `notification.py`, `task.py`, `__init__.py`, `user.py`)
- T009 + T010 (US1 service vs functional tests, different files) in parallel
- T018 + T019 (US2 service vs functional tests, different files) in parallel
- T026 + T027 (full suite vs constitution gate review) in parallel

---

## Parallel Example: User Story 1

```bash
# Launch US1 tests together (different files, no dependencies):
Task: "Service tests for transfer/reject/listing in tests/services/test_task_assignment_service.py"
Task: "Functional tests for assign + origin filter in tests/functional/test_assignment_routes.py"
```

## Parallel Example: User Story 2

```bash
# Launch US2 tests together (different files, no dependencies):
Task: "Service tests for unread/read-all/persistence in tests/services/test_notification_service.py"
Task: "Functional tests for notifications endpoints in tests/functional/test_notification_routes.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T002)
2. Complete Phase 2: Foundational (T003–T008)
3. Complete Phase 3: US1 tests-fail-first (T009–T010) then implementation (T011–T017)
4. **STOP and VALIDATE**: quickstart Escenarios A + B; `GET /tasks` without `origin` byte-compatible; `TASK_ASSIGNED` per transfer
5. Deploy/demo MVP (delegation without notification UI — notifications exist in DB via atomic creation)

### Incremental Delivery

1. Setup + Foundational → schema ready
2. Add US1 → test independently → Deploy/Demo (MVP: assign + transfer + audit)
3. Add US2 → test independently → Deploy/Demo (full collaboration: pending indicator + read history)
4. Polish → full quickstart A–D green, zero email/push, history persists

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (T001–T008)
2. Once Foundational is done:
   - Developer A: US1 implementation (T011–T017)
   - Developer B: US2 service + tests (T018, T020) seeded directly, then blueprint (T021–T024) once US1 T012 lands
3. Joint Polish (T025–T027)

---

## Notes

- [P] tasks = different files, no dependencies
- [US1]/[US2] labels map tasks to HU-10 / HU-11 for traceability
- Each user story independently completable and testable per its Independent Test
- Constitution Principle IV: tests fail before implementation; no story closes without green suite
- Commit after each task or logical group; stop at any checkpoint to validate independently
- Avoid: vague tasks, same-file conflicts, `db.create_all()` / manual DDL, blueprint→ORM shortcuts, frontend-only recipient validation
