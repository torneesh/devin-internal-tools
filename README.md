# devin-internal-tools

This prototype tests a claim: Devin on a small shared Python platform can replace the value of Microsoft Power Apps for a fintech team that plans to build 10+ internal tools. That value is speed combined with built-in governance. The argument is in [`docs/PITCH.md`](docs/PITCH.md), and this repo is the evidence for it.

What's here:
- **`core/`**: a shared platform that every tool inherits. It provides mock SSO with a user switcher, roles, an append-only audit log, central field masking with audited reveal, optimistic locking, state machines and approval rules, and adapters for external systems.
- **`tools/refunds/`**: the worked example of custom logic. It covers money movement with separation of duties, a two-approver threshold, idempotent execution, provider timeouts and reconciliation.
- **`tools/_template/`** and **[`AGENTS.md`](AGENTS.md)**: the starting point and the rules for every new tool.
- **Factory-built tools**: a KYC review queue and a feature-flag admin. Fresh Devin sessions built them in parallel, each from one business paragraph with no mention of the platform. Results, including what had to be fixed in review, are in [`docs/FACTORY_RESULTS.md`](docs/FACTORY_RESULTS.md).
- **[`BUILD_LOG.md`](BUILD_LOG.md)**: timestamps for every build block.

## Run it
Requires Python 3.11.

```bash
make setup   # creates .venv and installs requirements.txt
make run     # http://localhost:8000; deletes app.db and reseeds on every start
make test    # pytest: platform tests plus each tool's rule tests
make lint    # ruff check + ruff format --check (same checks as CI)
```

Sign in at `/login` by choosing a seeded user. This is mock SSO.

| User | Roles |
|---|---|
| alice | support_agent |
| bob, carol | refund_approver |
| dave, heidi | kyc_analyst |
| erin | kyc_supervisor |
| frank | engineer |
| grace | release_manager |
| ivan | auditor |
| admin | every role |

## 2-minute demo script
Each step maps to a demo moment in `docs/PITCH.md`.

**Pillar 1: governance is built once and every tool inherits it (≈40s)**
1. Sign in as **alice** (support agent). On the home page, the tools she can't use are greyed out as "No access". Open Refunds: she can request a refund, but she can't approve one or reveal a bank account.
2. Switch to **bob** (approver) and open refund `TXN-10412`. The bank account shows as `••••2606`. Click **Reveal**: you must give a reason, and the full value appears.
3. Switch to **ivan** (auditor) and open **Audit log** (`/audit`). The `reveal` event shows who revealed the value, when and why. Audit rows can't be edited or deleted, because database triggers reject `UPDATE` and `DELETE` on `audit_events`.
4. Change one masking rule. In `core/masking.py`, change `"refunds.bank_account"` from `mask=last4` to `mask=redact_all` and save. `make run` uses `--reload`, so the server restarts. Every refunds table and detail page now shows `••••••`. The database survives the reload, but the in-memory mock provider is reset. `tests/core/test_masking.py::test_changing_one_policy_changes_every_page` proves the same thing.

**Pillar 2: custom logic beyond the building blocks, with tests (≈40s)**

5. Self-approval: sign in as **admin**, request a refund, then try to approve it. The request is blocked: "You can't approve your own request (separation of duties)".
6. Two approvers over $1,000: as **bob**, approve `TXN-10388` ($2,400). It stays at 1 of 2 approvals. Bob can't approve it a second time. When **carol** approves, it moves to `APPROVED`.
7. Payment timeout without a double payment: as **bob**, open `TXN-10412` and set the provider mode to **timeout_after_accept**. Click **Execute payment**. The provider took the money but its response was lost, so the status is `UNKNOWN`, not `FAILED`. Click **Reconcile**. The platform looks up the payment by idempotency key, and the status becomes `SUCCEEDED`. If you click **Execute payment** again instead of reconciling, the same key is reused; `test_retry_never_pays_twice` checks that the provider was paid once (the mock has no ledger page).
8. Run `make test`. Each rule has a named test: `test_requester_cannot_approve_own_refund`, `test_retry_never_pays_twice` and the others. CI runs the same suite on every PR.

**Pillar 3: the tool factory (≈40s)**

9. Show `docs/FACTORY_RESULTS.md`. Two fresh sessions ran in parallel, and each was given only one paragraph. The table records elapsed time, PR links, which controls were inherited without being asked for, and what review had to fix.
10. Open **KYC queue** as **dave** (analyst). The government ID and date of birth are masked. There's no Reveal button until dave **claims** the case; then revealing needs a reason and is audited. Open **Feature flags** as **frank** (engineer), toggle a staging flag, then try production: frank gets no production controls. Switch to **grace** (release manager) to change production, then show the change history and one-click **Roll back to this**. Both behaviours came from review decisions recorded in `docs/FACTORY_RESULTS.md`.

## Architecture
```
app.py                 app factory: mounts core routers, discovers tools/*/router.py, creates tables, seeds
seed.py                users/roles + demo data per tool (seed_<tool>)
core/
  db.py                engine/session, VersionedMixin (id, version, created_at, updated_at)
  auth.py              mock SSO, CurrentUser, require_role (route) / ensure_role (service)
  audit.py             append-only AuditEvent, record() in the caller's transaction, /audit queries
  masking.py           FIELD_POLICIES["<table>.<column>"], mask(), audited reveal endpoint
  concurrency.py       update_versioned(): expected-version check -> 409 StaleWrite
  workflow.py          StateMachine, ApprovalPolicy (no self-approval, N distinct approvers)
  integrations.py      adapter registry for external systems (mocked locally and in tests)
  registry.py          register_tool() + home-page launcher filtered by role
  errors.py, ui.py     typed errors -> friendly pages with the right status; Jinja + shared macros
  templates/           base, macros (data_table, detail, masked_field, action_form, audit_trail), audit
tools/<name>/          models.py, service.py, router.py, templates/, tests/ (+ adapter mock if needed)
```

Each request goes through these steps. The route's `require_role` dependency checks the role. Then a service function runs `ensure_role`, checks the business rules and validates the state transition. It writes with `update_versioned` and `audit.record` in the same transaction, then commits. Templates use the shared macros, which apply `FIELD_POLICIES`, so a tool can't render a protected field unmasked by accident.

Stack: Python 3.11, FastAPI, SQLAlchemy 2.0, SQLite (the schema is Postgres-compatible), Jinja2, HTMX and Pico.css. There is no frontend build step. Tests use pytest, linting uses Ruff, and CI runs on GitHub Actions.

## Known gaps
This is a prototype, not a production platform.
- **Identity:** sign-in is a mock user picker with roles from `seed.py`. There's no real SSO (Entra/OIDC), MFA, group sync or session hardening.
- **Data:** it uses SQLite with `create_all`. There's no Postgres, no migrations (Alembic) and no backups. Append-only audit is enforced by SQLite triggers. Postgres would need equivalent triggers or grants, and that isn't built.
- **Integrations are mocks.** The payment provider and the flag service live in memory and reset when the app restarts (including the `--reload` in demo step 4), so flag pages can say SYNCED while the mock service is empty until the next push.
- **Masking:** a policy change is a code change and a deploy, not an admin setting. A reveal returns the raw value to the browser, and there's no rate limit or approval step for reveals.
- **No equivalent** of DLP policies, managed environments, deployment, monitoring or alerting. It hasn't had a pen test or a vendor security review. `docs/EVALUATION.md` sizes this work.
- **Governance relies on discipline.** Controls are inherited only if each tool follows `AGENTS.md`. Review and the required rule tests are the control point, as `docs/FACTORY_RESULTS.md` shows. Branch protection and required reviewers aren't configured in this repo.
- Out of scope by design: a drag-and-drop builder, pixel polish and mobile.
