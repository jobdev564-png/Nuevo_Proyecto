# Tasks: Interacción fluida del listado de tareas (Incremento 5)

**Input**: Design documents from `/specs/005-frontend-task-interactions/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/
**Tests**: Included per constitution Principle IV (test-first bloqueante) + plan R-06 + quickstart Q-5; frontend revert covered by manual blocking protocol Q-3/Q-4 (no JS runner in repo)
**Organization**: Tasks grouped by user story (US1 = HU-15, US2 = HU-16) for independent implementation and testing

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Baseline verification before any increment-5 change

- [X] T001 Verify clean baseline by running pytest tests/services/test_task_service.py tests/functional/test_task_routes.py -q from repo root
- [X] T002 [P] Read existing status contract in specs/001-basic-tasks-auth/contracts/task-contracts.md and lifecycle contract in specs/002-task-lifecycle-recovery/contracts/task-lifecycle-contracts.md
- [X] T003 [P] Read current list rendering in src/taskcontrol/templates/tasks/index.html and JS module in src/taskcontrol/static/js/main.js

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Persistent order column + deterministic listing order; MUST complete before US1/US2 work

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Create Alembic migration in migrations/versions/ adding `tasks.sort_order` with constraint verbatim `Integer, NOT NULL, DEFAULT 0` per specs/005-frontend-task-interactions/data-model.md
- [X] T005 Implement backfill in migrations/versions/ migration setting dense values `0..N-1` per `user_id` ordered by `created_at, id` tiebreak per specs/005-frontend-task-interactions/data-model.md and research.md R-05
- [X] T006 Add `sort_order` column to Task model in src/taskcontrol/models/task.py with `NOT NULL, DEFAULT 0` and include it in `to_dict()` output
- [X] T007 Update `get_user_tasks()` in src/taskcontrol/services/task_service.py to order `ORDER BY sort_order ASC, id ASC` within user+filter, and set new-task rule `sort_order = max(propietario)+1` (new tasks at end) per specs/005-frontend-task-interactions/data-model.md
- [X] T008 [P] Add foundational service test in tests/services/test_task_service.py verifying backfill order is dense `0..N-1` per user and new task lands at `max+1`
- [X] T009 Apply migration locally and re-run pytest tests/services/test_task_service.py -q from repo root to confirm green baseline

**Checkpoint**: Foundation ready — `tasks.sort_order` exists, listing is deterministic, user story work can begin

---

## Phase 3: User Story 1 — Marcar tarea como completada sin recarga (HU-15) (Priority: P1) 🎯 MVP

**Goal**: Complete button per row calls existing `POST /tasks/<id>/status` via `fetch` with optimistic update and guaranteed revert on failure (FR-001–FR-005, FR-012–FR-015)

**Independent Test**: Open list with one pending/in_progress task, action complete control, row shows completed without full reload; after manual reload the completed state persists; with backend stopped the row reverts and shows a non-technical error (quickstart Q-1, Q-3)

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T010 [P] [US1] Add service regression test in tests/services/test_task_service.py for direct jump `pending → completed` and `in_progress → completed` via `TaskService.update_task_status()` in src/taskcontrol/services/task_service.py (salto directo aclarado 2026-10-11)
- [X] T011 [P] [US1] Add route contract test in tests/functional/test_task_routes.py for `POST /tasks/<id>/status` with JSON `{"status": "completed"}` expecting envelope `{status, message, data}` with 200 success, 400 `INVALID_STATE_TRANSITION`, 404 `TASK_NOT_FOUND` neutral, 401 without session in src/taskcontrol/routes/tasks.py

### Implementation for User Story 1

- [X] T012 [US1] Add per-row complete control with `data-task-id` attribute in src/taskcontrol/templates/tasks/index.html reusing base flow with reload as fallback (FR-015 degradation)
- [X] T013 [US1] Implement complete-without-reload in src/taskcontrol/static/js/main.js using native `fetch` against `POST /tasks/<id>/status` with `Accept: application/json`, optimistic snapshot (`previousStatus`, classes, filter position), control disabled until response to neutralize double-click per research.md R-01
- [X] T014 [US1] Implement revert-on-failure in src/taskcontrol/static/js/main.js restoring snapshot and showing non-technical message on `!response.ok`, network exception, or `status: error`, with re-login hint on 401 per spec FR-003/FR-004 and research.md R-01
- [X] T015 [US1] Verify `STATUS_CHANGED` audit path in src/taskcontrol/services/task_service.py and src/taskcontrol/services/audit_service.py emits `actor_id, action, entity_id, timestamp ISO-8601 UTC` on every HU-15 mutation (no new audit action)
- [X] T016 [US1] Execute manual blocking protocol Q-1 and Q-3 from specs/005-frontend-task-interactions/quickstart.md (success without reload; offline + expired-session + double-click revert, zero false states)

**Checkpoint**: US1 fully functional and independently testable — completing works without reload, failures always revert

---

## Phase 4: User Story 2 — Reordenar tareas arrastrando y soltando (HU-16) (Priority: P2)

**Goal**: Native drag-and-drop (+ keyboard up/down buttons) with immediate persistence per filtered view via `POST /tasks/reorder` and per-user order surviving reload (FR-006–FR-015, aclaraciones orden-por-vista, nuevas-al-final, botones teclado, auditoría por persistencia)

**Independent Test**: Open list with ≥3 tasks, drag one to new position, drop, list shows new order instantly; after reload order is identical; second user list unaffected; up/down buttons replicate by keyboard; with backend stopped the list reverts with error (quickstart Q-2, Q-4)

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T017 [P] [US2] Add service test in tests/services/test_task_service.py for `TaskService.reorder_tasks()` in src/taskcontrol/services/task_service.py verifying dense renumber `sort_order = 0..N-1` in received order, per-view scoping (tasks outside view keep value), and new task at end per specs/005-frontend-task-interactions/data-model.md
- [X] T018 [P] [US2] Add service rejection test in tests/services/test_task_service.py verifying batch with foreign/nonexistent/deleted id or duplicates rejects the whole batch with nothing written per specs/005-frontend-task-interactions/contracts/order-contracts.md (`404` neutral, `400 ORDER_INCOMPLETE`/`ORDER_DUPLICATE`)
- [X] T019 [P] [US2] Add route contract test in tests/functional/test_task_routes.py for `POST /tasks/reorder` in src/taskcontrol/routes/tasks.py with payload `{"ordered_ids": [...], "view": "pending"}` expecting 200 `{status: success, data: {ordered_ids, view}}`, 400 `VALIDATION_ERROR`/`ORDER_INCOMPLETE`, 401 `UNAUTHORIZED`, 404 `TASK_NOT_FOUND`, plus `AuditLog(TASK_ORDER_CHANGED)` emission

### Implementation for User Story 2

- [X] T020 [US2] Implement `TaskService.reorder_tasks(user_id, ordered_ids, view)` in src/taskcontrol/services/task_service.py validating ownership/liveness/duplicates/completeness-against-view, writing dense `0..N-1` atomically, emitting one `TASK_ORDER_CHANGED` audit per persistence via src/taskcontrol/services/audit_service.py
- [X] T021 [US2] Implement `POST /tasks/reorder` (plus optional `PATCH` alias, JSON only) in src/taskcontrol/routes/tasks.py registered before `/tasks/<id>` routes, requiring `login_required` session, accepting `application/json` and `application/x-www-form-urlencoded` degradation, returning `{status, message?, data?, code?}` envelope per specs/005-frontend-task-interactions/contracts/order-contracts.md
- [X] T022 [P] [US2] Make rows draggable with `draggable`, `data-task-id`, `data-sort-order` attributes and add per-row subir/bajar keyboard-operable buttons in src/taskcontrol/templates/tasks/index.html reusing the same persistence routine (FR-015 accessible alternative)
- [X] T023 [US2] Implement drag-and-drop persistence in src/taskcontrol/static/js/main.js handling `dragstart/dragover/drop/dragend`, sending `ordered_ids` of current filtered view immediately after drop (or button action), reverting to prior confirmed order and showing non-technical message on `4xx/5xx`/network failure and re-login hint on 401 per spec FR-010
- [X] T024 [US2] Execute manual blocking protocol Q-2 and Q-4 from specs/005-frontend-task-interactions/quickstart.md (5-task persistence across reload, cross-user isolation, keyboard buttons, failure revert)

**Checkpoint**: US1 AND US2 both work independently — complete-without-reload and drag-reorder each survive reload and never leave false states

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Release readiness across both stories

- [X] T025 Run automated blocking suite via pytest tests/services/test_task_service.py tests/functional/test_task_routes.py -q from repo root per specs/005-frontend-task-interactions/quickstart.md Q-5
- [X] T026 [P] Run full quickstart validation Q-1 through Q-5 from specs/005-frontend-task-interactions/quickstart.md and record results
- [X] T027 [P] Security review of src/taskcontrol/routes/tasks.py and src/taskcontrol/services/task_service.py confirming server-side auth/ownership per task, backend validation of transitions and positions, no client-trusted values, no secrets in logs/responses per constitution VII
- [X] T028 Review requirements-quality checklist in specs/005-frontend-task-interactions/checklists/frontend.md and resolve reviewer findings, prioritizing CHK010 (spec vs plan endpoint deviation)
- [X] T029 Code cleanup in src/taskcontrol/static/js/main.js, src/taskcontrol/templates/tasks/index.html, src/taskcontrol/services/task_service.py removing dead reload paths while keeping SSR base-flow degradation intact

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (T004→T009 sequential: migration before model/service/listing)
- **User Stories (Phase 3–4)**: Depend on Foundational completion
  - US1 (P1) then US2 (P2) in priority order; parallel staffing possible after foundation
- **Polish (Phase 5)**: Depends on all desired stories complete

### User Story Dependencies

- **User Story 1 (P1, HU-15)**: Starts after Foundational — no dependency on US2; reuses existing `POST /tasks/<id>/status`, zero schema/endpoint additions
- **User Story 2 (P2, HU-16)**: Starts after Foundational — needs `sort_order` + new `POST /tasks/reorder`; independently testable from US1 (reorder works regardless of complete-without-reload, and vice versa)

### Within Each User Story

- Tests MUST be written and FAIL before implementation (constitution IV Red-Green-Refactor)
- Service before routes; routes before templates/JS; core before revert/error paths
- Manual blocking protocol (Q-3 for US1, Q-4 for US2) before story sign-off (no JS runner per R-06)

### Parallel Opportunities

- Phase 1: T002, T003 in parallel
- Phase 2: T008 in parallel with T004–T007 implementation (different files)
- US1 tests: T010, T011 in parallel (tests/services/test_task_service.py vs tests/functional/test_task_routes.py)
- US2 tests: T017, T018, T019 in parallel (all different test scopes, same files but additive cases — coordinate appends)
- T022 (template) can run in parallel with T020–T021 (service/route) once contracts are fixed
- US1 and US2 can be staffed in parallel after Phase 2 by different developers (disjoint primary files: status path vs reorder path, shared only main.js — merge carefully)

---

## Parallel Example: User Story 1

```bash
# Launch US1 tests together (different files, no dependency):
Task: "Add service regression test in tests/services/test_task_service.py for direct jump pending→completed via TaskService.update_task_status()"
Task: "Add route contract test in tests/functional/test_task_routes.py for POST /tasks/<id>/status envelope"

# Launch US2 tests together after foundation:
Task: "Add service test in tests/services/test_task_service.py for TaskService.reorder_tasks() dense 0..N-1 per-view"
Task: "Add route contract test in tests/functional/test_task_routes.py for POST /tasks/reorder ordered_ids/view envelope"
```

## Parallel Example: User Story 2

```bash
# Service + route implementation can overlap template work once T019 contract is fixed:
Task: "Implement TaskService.reorder_tasks() in src/taskcontrol/services/task_service.py"
Task: "Make rows draggable with data-task-id/data-sort-order + subir/bajar buttons in src/taskcontrol/templates/tasks/index.html"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational (T004–T009) — migration + deterministic listing (needed even for MVP display stability)
3. Complete Phase 3: US1 (T010–T016)
4. **STOP and VALIDATE**: quickstart Q-1 + Q-3 + Q-5 (status path); demo complete-without-reload with revert guarantee
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → deterministic ordered listing ready
2. Add US1 → test independently (Q-1/Q-3) → Deploy/Demo (MVP: fluid completion)
3. Add US2 → test independently (Q-2/Q-4) → Deploy/Demo (full increment: + persistent manual order)
4. Polish → full Q-1–Q-5 green + security + checklist review

### Parallel Team Strategy

1. Team completes Setup + Foundational together (migration is single-writer)
2. Once foundation done:
   - Developer A: US1 (status fetch + revert in src/taskcontrol/static/js/main.js + row control)
   - Developer B: US2 (reorder service + route + DnD in same JS/template files — coordinate via contract-first: fix `ordered_ids/view` payload, then merge)
3. Joint sign-off on shared files (src/taskcontrol/templates/tasks/index.html, src/taskcontrol/static/js/main.js) + full suite

---

## Notes

- [P] tasks = different files, no dependencies (exception: additive test appends to same file need coordination)
- [US1]/[US2] labels map to HU-15/HU-16 for traceability
- Constitution gates enforced: II (JS → routes/tasks.py → services/task_service.py → models/task.py, no ORM in blueprints), III (reorder contract in contracts/order-contracts.md before code), VI (versioned migration only), VII (server-side auth+validation), VIII (STATUS_CHANGED + TASK_ORDER_CHANGED audit)
- Known deviation documented in plan/research R-03: spec phrase "ningún endpoint nuevo" vs required minimal `POST /tasks/reorder` — flagged in checklists/frontend.md CHK010, must be acknowledged before US2 sign-off
- Stop at any checkpoint to validate story independently with quickstart.md
