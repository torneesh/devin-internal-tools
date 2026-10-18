# AGENTS.md: rules for building a tool on this platform

This repo is a shared internal-tools platform (`core/`) plus tools (`tools/<name>/`). Each tool
inherits sign-in, roles, audit, field masking, optimistic locking and approvals from `core/`.
Follow these rules for every new tool or change. `tools/refunds/` is the full worked example.

## Setup and checks
- `make setup` (Python 3.11 venv), `make run` (http://localhost:8000, fresh seeded DB on every start),
  `make test`, `make lint`, `make fmt`.
- Both `make test` and `make lint` must pass before you open a PR. CI runs the same checks.

## Rules
1. **Start from the template.** Copy `tools/_template` to `tools/<name>` and rename `Item`, the table
   (`<name>_<things>`) and the imports. The folder name becomes the URL prefix. Call `register_tool`
   in `router.py` so the tool appears on the home page. `app.py` discovers `tools/*/router.py`
   automatically, so don't edit `app.py`.
2. **Roles.** Put `Depends(require_role(...))` on every route, and call `ensure_role(user, ...)` at the
   top of every service function. Use the existing roles in `seed.py` where they fit. Add new roles
   to `ROLES` and users to `USERS` in `seed.py` (the `admin` user gets every role automatically). Add
   demo data with a `seed_<name>(db)` function in `seed.py` that calls your service functions.
3. **Models and writes.** Every model uses `VersionedMixin`. Business logic lives in `service.py`.
   Service functions take `(db, user, ...)` and follow this order: check role, check rules, change,
   `audit.record(...)`, `db.commit()`. Every change to an existing row goes through
   `update_versioned(db, obj, expected_version, ...)`, which returns `before` for the audit call.
   Forms send the record's `version` (`action_form` does this), so stale writes get a 409.
4. **Sensitive fields** (government IDs, bank details, dates of birth, emails, phone numbers,
   addresses, secrets) **must** have an entry in `FIELD_POLICIES` in `core/masking.py`, keyed
   `"<table>.<column>"`, with a mask function and the roles allowed to reveal. Render them with the
   `detail` / `data_table` / `masked_field` macros. Never print them raw in templates, flash
   messages or logs. Revealing a value needs a reason and is audited automatically, and audit
   events store masked values. Adding a `FIELD_POLICIES` entry is the one `core/` edit a tool
   normally needs.
5. **Status changes** go through a `StateMachine` (`FLOW.check(current, target)`). Approvals use
   `ApprovalPolicy`: no self-approval, and distinct approvers above a threshold. Decisions that
   need a reason (reject, escalate, ...) store it and pass it as `reason=` to `audit.record`.
6. **External systems** go behind an adapter: a class with a `name`, registered with
   `integrations.register(...)` at import. Put the mock in the tool folder (see
   `tools/refunds/provider.py`). Services get it with `integrations.get(name)` and accept an
   optional adapter argument so tests can pass a fresh mock.
7. **Tests are required** in `tools/<name>/tests/` (keep the `__init__.py`): at least one
   permission test per action, one test per business rule (named after the rule), a stale-write
   test, and an audit test showing every mutation is recorded. A masking test is required for each
   protected field. Use the fixtures in `conftest.py`: `db`, `user("bob")`, `login("bob")`,
   `client`.
8. **Don't change `core/`** (apart from rule 4) unless you have to. If you do, say so explicitly in
   the PR description and explain why.
9. **PR description** lists: roles (who can do what), business rules, sensitive fields and their
   policies, any `core/` changes, and how to demo it (which seeded users, which clicks).

## UI conventions
- Templates extend `base.html` and `{% import "macros.html" as ui %}`. Render with
  `page(request, f"{T}/x.html", ...)`, where `T = f"{TOOL}/templates"`.
- Reuse `ui.data_table`, `ui.detail`, `ui.action_form`, `ui.status_badge` and `ui.audit_trail`. Show
  the record's audit trail on its detail page.
- Raise `core.errors` exceptions (`PermissionDenied`, `NotFound`, `ValidationError`,
  `RuleViolation`, `InvalidTransition`, `StaleWrite`). The platform renders them with the right
  HTTP status.
- POST, then redirect (303) back, with a `flash(request, ...)` message.
