# Tasks: 003-task-organization-priority — Organización y Priorización de Tareas (HU-07, HU-08, HU-09)

**Input**: Design documents from `/specs/003-task-organization-priority/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/
**Tests**: YES — explicitly requested (SC-007: 100% coverage of priority/category/overdue service logic before enabling HTTP routes; plan.md §6 blocking tests; Constitution Principle IV test-first). All service test tasks MUST be written FIRST and FAIL before implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Single project monolito: `src/taskcontrol/`, `tests/`, `migrations/` at repository root
- Structure per plan.md: `models/`, `services/`, `routes/`, `templates/`, `static/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Baseline verification and work environment readiness

- [X] T001 Verify baseline state: run existing suite `pytest tests/ -q` and `flask --app src.taskcontrol db current` from repo root, confirm green before changes
- [X] T002 [P] Review quickstart prerequisites in specs/003-task-organization-priority/quickstart.md (Python 3.11+, venv, requirements installed)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Versioned schema migration that MUST be complete before ANY user story implementation (Principle VI)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 Create Alembic migration in migrations/versions/c3d4e5f6a7b8_task_organization_priority.py: create `categories` table (id, user_id FK users.id ON DELETE CASCADE, name VARCHAR(50) NOT NULL, description TEXT NULL, created_at DATETIME NOT NULL, UniqueConstraint user_id+name `uq_user_category_name`, index ix_categories_user_id) and batch_alter_table `tasks` adding `priority` VARCHAR(10) NOT NULL with server_default='medium' plus `category_id` INTEGER NULL with index ix_tasks_category_id and FK to categories.id ON DELETE SET NULL
- [X] T004 Apply and verify migration from repo root (`flask --app src.taskcontrol db upgrade`, then downgrade/upgrade roundtrip on a scratch SQLite DB): pre-existing tasks acquire `'medium'` with zero NULL violations

**Checkpoint**: Foundation ready — `tasks.priority` defaults to `'medium'`, `tasks.category_id` nullable, `categories` table exists — user story implementation can now begin

---

## Phase 3: User Story 1 — Priorización de Tareas y Ordenamiento (HU-07) (Priority: P1) 🎯 MVP

**Goal**: Tasks carry priority `high`/`medium`/`low` (default `medium`), list can be ordered by priority (either direction, deterministic tiebreak), owner can change priority anytime with audit.

**Independent Test**: Create tasks with high/medium/low plus one with no priority (must store `medium`); list with `sort_by=priority&order=desc` returns high → medium → low combined with a status filter; update one task's priority and verify persistence + `TASK_PRIORITY_CHANGED` audit row; invalid priority rejected with validation message.

### Tests for User Story 1 (test-first, MUST fail before implementation) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T005 [US1] Service tests for priority in tests/services/test_task_service.py: `test_default_priority_is_medium` (omit priority → `'medium'`), `test_invalid_priority_rejected` (value outside set raises `TaskValidationError("Prioridad inválida. Debe ser 'high', 'medium' o 'low'")`), `test_tasks_ordered_by_priority_desc` (high → medium → low), `test_tasks_ordered_by_priority_asc` (low → medium → high), `test_tasks_order_with_status_filter` (priority order AND status filter combined), tiebreak by due_date asc then id desc
- [X] T006 [P] [US1] Route tests for priority endpoints in tests/functional/test_task_routes.py: POST `/tasks/<id>/priority` success (200/302) and invalid value (400 `"Prioridad inválida. Debe ser 'high', 'medium' o 'low'."`), unknown/foreign task (404 `"Tarea no encontrada."`), GET `/tasks/?sort_by=priority&order=desc` ordering

### Implementation for User Story 1

- [X] T007 [P] [US1] Extend Task model with `priority = db.Column(db.String(10), nullable=False, default="medium", server_default="medium")` in src/taskcontrol/models/task.py (admissible set verbatim `{"high", "medium", "low"}`)
- [X] T008 [US1] Extend TaskService in src/taskcontrol/services/task_service.py: `create_task()` accepts optional priority defaulting to `"medium"` with validation raising `TaskValidationError("Prioridad inválida. Debe ser 'high', 'medium' o 'low'")`; add `update_task_priority()` that blocks deleted tasks (`TaskDeletedError`), persists change and logs `TASK_PRIORITY_CHANGED` with `{"old_priority": old, "new_priority": new}` via audit_service
- [X] T009 [US1] Extend `TaskService.get_user_tasks()` in src/taskcontrol/services/task_service.py with `sort_by`/`order` params: `sort_by="priority"` orders via CASE expression (`{"high": 1, "medium": 2, "low": 3}`, desc = high → low) with deterministic tiebreak `Task.due_date.asc(), Task.id.desc()`; no `sort_by` keeps legacy `Task.created_at.desc()`; always excludes `is_deleted`
- [X] T010 [US1] Extend tasks blueprint in src/taskcontrol/routes/tasks.py: `POST /tasks/<int:task_id>/priority` (login required, 400/404 JSON errors per contracts), create/edit accept optional `priority`, list reads `sort_by`/`order` query params and delegates to `TaskService` (never queries ORM directly, Principle II)
- [X] T011 [US1] Extend task templates src/taskcontrol/templates/tasks/index.html (priority badges high→"Alta"/medium→"Media"/low→"Baja", sort selector `sort_by=priority` + order) and src/taskcontrol/templates/tasks/edit.html (priority select field)
- [X] T012 [P] [US1] Add priority badge styles (alta/media/baja) in src/taskcontrol/static/css/styles.css

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently (quickstart Escenario A passes)

---

## Phase 4: User Story 2 — Agrupación en Categorías y Desvinculación Segura (HU-08) (Priority: P2)

**Goal**: Users create private categories, link each task to at most one category (or none), filter by category; deleting a category unlinks (SET NULL) and NEVER cascade-deletes tasks; cross-user category use rejected.

**Independent Test**: Create own category, link tasks, verify a task holds at most one category and unlink sets "sin categoría"; delete a populated category and verify 100% of its tasks survive with `category_id = None` + `CATEGORY_DELETED` audit; duplicate name for same user rejected (409) while same name across users allowed; foreign `category_id` rejected.

### Tests for User Story 2 (test-first, MUST fail before implementation) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T013 [US2] Service tests for categories in tests/services/test_category_service.py: `test_category_name_unique_per_user` (duplicate own name rejected case-insensitively, same name by different user allowed), `test_delete_category_unlinks_tasks_and_does_not_delete_them` (tasks survive with `category_id is None`, `unlinked_tasks_count` audited), `test_cannot_assign_foreign_category` (assigning another user's category raises validation/not-found), empty/blank name and name > 50 chars rejected
- [X] T014 [P] [US2] Route tests for category endpoints in tests/functional/test_category_routes.py: GET `/categories/` lists only own categories; POST `/categories/` success (201) / empty name (400 `"El nombre de la categoría es obligatorio y debe tener como máximo 50 caracteres."`) / duplicate (409 `"Ya existe una categoría con ese nombre en su cuenta."`); POST `/categories/<id>/delete` success unlink response and foreign id (404 `"Categoría no encontrada."`); unauthenticated → redirect/401

### Implementation for User Story 2

- [X] T015 [P] [US2] Create Category model in src/taskcontrol/models/category.py: `id` INTEGER PK autoincrement, `user_id` INTEGER FK users.id ON DELETE CASCADE NOT NULL indexed, `name` VARCHAR(50) NOT NULL (verbatim: "No puede ser nulo, vacío ni contener solo espacios en blanco. Longitud máxima: 50 caracteres."), `description` TEXT nullable, `created_at` DATETIME NOT NULL default UTC, `UniqueConstraint("user_id", "name", name="uq_user_category_name")`
- [X] T016 [P] [US2] Extend Task model with category FK in src/taskcontrol/models/task.py: `category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)` plus `category = db.relationship("Category", backref=db.backref("tasks", lazy="dynamic"))` (NULL = "sin categoría")
- [X] T017 [US2] Create CategoryService in src/taskcontrol/services/category_service.py: `create_category` (strip name, reject blank/>50, case-insensitive per-user uniqueness check, log `CATEGORY_CREATED` with `{"name": name}`), `get_user_categories` (own only, order name ASC), `delete_category` (verify ownership, explicitly run `Task.query.filter_by(category_id=category_id).update({Task.category_id: None})` before `db.session.delete(category)`, log `CATEGORY_DELETED` with `{"name": name, "unlinked_tasks_count": N}`)
- [X] T018 [US2] Extend TaskService category assignment in src/taskcontrol/services/task_service.py: `update_task_category()` validates category exists and verbatim `category.user_id == task.user_id` else raises `TaskValidationError`/`CategoryNotFoundError` ("La categoría indicada no existe o no pertenece a su usuario."), accepts null/empty → None, blocks deleted tasks, logs `TASK_CATEGORY_CHANGED` with `{"old_category_id": old, "new_category_id": new}`
- [X] T019 [US2] Create categories blueprint in src/taskcontrol/routes/categories.py: `GET /categories/` (render categories/index.html + JSON), `POST /categories/` (400/409 JSON errors per contracts), `POST /categories/<int:category_id>/delete` (200 JSON with `deleted_category_id` + `unlinked_tasks`, 404 for foreign), all `@login_required`, delegating to `CategoryService` only
- [X] T020 [US2] Wire blueprint and exports: register `categories_bp` with url_prefix `/categories` in src/taskcontrol/__init__.py and export `Category` in src/taskcontrol/models/__init__.py
- [X] T021 [US2] Create categories template src/taskcontrol/templates/categories/index.html (list ordered name ASC, create form, delete confirmation with "Las tareas asociadas ahora están sin categoría") and extend src/taskcontrol/templates/base.html navbar with "Categorías" link
- [X] T022 [US2] Extend tasks blueprint with `POST /tasks/<int:task_id>/category` in src/taskcontrol/routes/tasks.py (null/empty → unlink, 400 for foreign category, 404 for foreign task) and extend src/taskcontrol/templates/tasks/index.html + src/taskcontrol/templates/tasks/edit.html with category label/dropdown including "Sin categoría" option

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently (quickstart Escenarios A + B pass; SC-003 zero cascade deletes verified)

---

## Phase 5: User Story 3 — Indicación Determinista de Tareas Vencidas desde el Backend (HU-09) (Priority: P3)

**Goal**: Backend computes `is_overdue` per task (strictly past UTC due date AND not completed AND not deleted AND has due date) and exposes it in the data contract; frontend renders the badge with zero date math in JavaScript.

**Independent Test**: Tasks with past due date in `pending`/`in_progress` → `is_overdue = true`; past due + `completed` → `false`; no due date → `false`; due today → `false`; logically deleted → `false`; contract JSON contains `is_overdue`; page HTML shows badge without any `new Date()` comparison in main.js.

### Tests for User Story 3 (test-first, MUST fail before implementation) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T023 [US3] Service/model tests for overdue in tests/services/test_task_service.py: `test_overdue_when_due_date_passed_and_pending` (yesterday + pending → True), `test_never_overdue_when_completed` (yesterday + completed → False, BLOCKING), `test_never_overdue_when_today_or_future` (today/tomorrow → False), `test_never_overdue_when_no_due_date` (None → False), deleted task → False
- [X] T024 [P] [US3] Contract tests for overdue exposure in tests/functional/test_task_routes.py: GET `/tasks/` JSON items contain boolean `is_overdue` matching server-date rules; completed past-due item returns `false`

### Implementation for User Story 3

- [X] T025 [P] [US3] Implement `is_overdue` derived property on Task in src/taskcontrol/models/task.py (verbatim rules: completed → false; `is_deleted` → false; `due_date` NULL → false; `due_date < datetime.now(timezone.utc).date()` → true else false; NEVER a DB column) and include `"is_overdue": self.is_overdue` in `to_dict()` in src/taskcontrol/models/task.py
- [X] T026 [US3] Render overdue badge from server data in src/taskcontrol/templates/tasks/index.html (Jinja2 reads `task.is_overdue` directly, "Vencida" badge + CSS class) and verify src/taskcontrol/static/js/main.js performs no due-date/overdue computation (display-only consumption of backend boolean)
- [X] T027 [P] [US3] Add overdue badge style in src/taskcontrol/static/css/styles.css

**Checkpoint**: All of User Stories 1–3 independently functional (quickstart Escenarios A + B + C pass; SC-004 zero client-side computation)

---

## Phase 6: User Story 4 — Consulta Integrada: Filtrado por Categoría y Estado con Orden por Prioridad (Priority: P3)

**Goal**: Combined `status` + `category_id` (incl. `"none"`/`"uncategorized"`) + `sort_by=priority` query on the task list, satisfying all criteria simultaneously (AND).

**Independent Test**: Seed diverse tasks, query `status=pending` + specific `category_id` + `sort_by=priority` and assert every row meets all three; `category_id=none` returns only uncategorized; `status=en_progreso` + category + priority order combined.

### Tests for User Story 4 (test-first, MUST fail before implementation) ⚠️

- [X] T028 [US4] Combined-filter tests in tests/functional/test_task_routes.py: category-specific + priority order, `"none"`/`"uncategorized"` returns only `category_id IS NULL` rows, triple combination status+category+priority, and backward compatibility (no new params → legacy behavior identical to increments 1–2)

### Implementation for User Story 4

- [X] T029 [US4] Extend `TaskService.get_user_tasks()` signature in src/taskcontrol/services/task_service.py to `(user_id, status=None, category_id=None, sort_by=None, order="desc")`: integer `category_id` filters equality, `"none"`/`"uncategorized"` filters `Task.category_id.is_(None)`, filters accumulate with AND, default order unchanged when `sort_by` absent
- [X] T030 [US4] Extend `GET /tasks/` handler in src/taskcontrol/routes/tasks.py to parse/sanitize `status`, `category_id`, `sort_by`, `order` from `request.args`, pass to service, and inject `categories`, `current_status`, `current_category_id`, `current_sort_by`, `current_order` into the Jinja2 context
- [X] T031 [US4] Extend filter/sort UI in src/taskcontrol/templates/tasks/index.html (category dropdown incl. "Sin categoría", preserve active status filter when sorting per FR-007)

**Checkpoint**: All user stories independently functional; combined query satisfies FR-005/FR-006/FR-007/FR-013

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Contract compliance, audit completeness, performance gates, and end-to-end validation

- [X] T032 Run full blocking suites from repo root (`pytest tests/services/test_task_service.py tests/services/test_category_service.py tests/functional/test_task_routes.py tests/functional/test_category_routes.py -v`) and fix regressions
- [X] T033 [P] Verify audit completeness in src/taskcontrol/services/audit_service.py usage: every mutation emits rows with `actor_id`, `action` (`CATEGORY_CREATED`, `CATEGORY_DELETED`, `TASK_PRIORITY_CHANGED`, `TASK_CATEGORY_CHANGED`), `entity_id`, ISO-8601 UTC `timestamp` (SC-006)
- [X] T034 [P] Verify security isolation: all routes in src/taskcontrol/routes/categories.py and new handlers in src/taskcontrol/routes/tasks.py enforce `@login_required` + `user_id` ownership on tasks and categories (IDOR rejection, SC-005)
- [X] T035 Validate performance gate SC-002: seed 500 tasks for one user, assert priority-ordered list responds deterministically in < 1 s (tiebreak stable across requests)
- [X] T036 Run quickstart.md end-to-end validation (Escenarios A, B, C) against a migrated dev DB and record results
- [X] T037 Code cleanup: remove dead code, align presentation mapping (high→"Alta", medium→"Media", low→"Baja") across templates, confirm no `is_overdue` persistence or JS date logic

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories (migration must apply cleanly)
- **User Stories (Phases 3–6)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P3)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 — HU-07 (P1)**: Can start after Foundational (Phase 2) — No dependencies on other stories
- **User Story 2 — HU-08 (P2)**: Can start after Foundational (Phase 2) — May integrate with US1 (priority+category display) but independently testable; owns the `categories` table created in Phase 2
- **User Story 3 — HU-09 (P3)**: Can start after Foundational (Phase 2) — Independent derived property; no dependency on US1/US2
- **User Story 4 — Integrated query (P3)**: Depends CONCEPTUALLY on US1 (priority sort) + US2 (category filter) service behavior — implement after Phases 3–4, or by the same developer incrementally

### Within Each User Story

- Tests MUST be written and FAIL before implementation (Principle IV, SC-007)
- Models before services
- Services before endpoints (routes delegate to services, never ORM directly)
- Core implementation before integration
- Story complete (checkpoint scenario green) before moving to next priority

### Parallel Opportunities

- Phase 1: T002 can run alongside T001
- Phase 2: sequential (single migration file)
- Once Foundational completes, US1/US2/US3 can start in parallel (different files: task_service priority vs category_service vs task model property — note US1-T008/US2-T018/US3-T025 share files, so parallelize by story-owner with sequential merge, or run US3 tests + US2 model while US1 implements)
- Route tests (`tests/functional/test_category_routes.py`) parallel with service tests (`tests/services/test_category_service.py`); templates parallel with routes; CSS parallel with everything
- Phase 7: T033 and T034 can run in parallel (audit vs security review, different concerns)

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together (different files, no dependencies):
Task: "Service tests for priority in tests/services/test_task_service.py" (T005)
Task: "Route tests for priority endpoints in tests/functional/test_task_routes.py" (T006)

# Launch model + styles for User Story 1 together (different files):
Task: "Extend Task model with priority column in src/taskcontrol/models/task.py" (T007)
Task: "Add priority badge styles in src/taskcontrol/static/css/styles.css" (T012)
```

## Parallel Example: User Story 2

```bash
# Launch all tests for User Story 2 together (different files):
Task: "Service tests for categories in tests/services/test_category_service.py" (T013)
Task: "Route tests for category endpoints in tests/functional/test_category_routes.py" (T014)

# Launch both model tasks together (different concerns, coordinated merge into task.py):
Task: "Create Category model in src/taskcontrol/models/category.py" (T015)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T002)
2. Complete Phase 2: Foundational (T003–T004, CRITICAL — migration green)
3. Complete Phase 3: User Story 1 (T005–T012, HU-07 priority)
4. **STOP and VALIDATE**: Test US1 independently (default `medium`, desc/asc order, invalid rejected, audit row) + quickstart Escenario A
5. Deploy/demo if ready — prioritization delivers standalone value on existing task lists

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US1 (HU-07 priority) → Test independently → Deploy/Demo (MVP!)
3. Add US2 (HU-08 categories) → Test independently incl. zero-cascade proof → Deploy/Demo
4. Add US3 (HU-09 overdue) → Test independently incl. completed-exclusion → Deploy/Demo
5. Add US4 (integrated query) → Test combined filters → Deploy/Demo
6. Each story adds value without breaking previous stories (backward-compatible list endpoint)

### Parallel Team Strategy

With multiple developers (after Setup + Foundational done together):

1. Developer A: User Story 1 (priority service + task routes + task templates)
2. Developer B: User Story 2 (Category model/service + categories blueprint + templates)
3. Developer C: User Story 3 (is_overdue property + contract exposure + badge)
4. Coordinate shared-file merges in `src/taskcontrol/models/task.py`, `src/taskcontrol/services/task_service.py`, `src/taskcontrol/routes/tasks.py` (US1 first, then US2/US3 rebase)
5. US4 + Polish together after stories merge

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability (US1=HU-07, US2=HU-08, US3=HU-09, US4=integrated)
- Each user story is independently completable and testable (see Independent Test per phase)
- Verify tests fail before implementing (Red-Green-Refactor, Principle IV)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Verbatim domain constraints embedded in tasks: priority set `{"high", "medium", "low"}` + `TaskValidationError("Prioridad inválida. Debe ser 'high', 'medium' o 'low'")`; category name "No puede ser nulo, vacío ni contener solo espacios en blanco. Longitud máxima: 50 caracteres." + `UniqueConstraint("user_id", "name")`; FK `ondelete="SET NULL"` + explicit service-level unlink; overdue decision table from data-model.md §3.1
- Avoid: vague tasks, same-file parallel edits, cross-story dependencies that break independence, direct ORM in blueprints, JS date math for overdue
