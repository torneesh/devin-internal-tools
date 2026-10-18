# devin-internal-tools

This prototype tests a claim: Devin on a small shared Python platform can replace the value of Microsoft Power Apps for a fintech team that plans to build 10+ internal tools. That value is speed combined with built-in governance. The argument is in [`docs/PITCH.md`](docs/PITCH.md), and this repo is the evidence for it.

What's here:
- **`core/`**: a shared platform that every tool inherits. It provides real OIDC sign-in (a local Keycloak stands in for Entra ID or Okta) with identity-provider groups mapped to roles, a mock user switcher for tests, roles, an append-only audit log, central field masking with audited reveal, optimistic locking, state machines and approval rules, adapters for external systems, and a shared Fluent-style UI shell: header, role-filtered left menu and a stage bar for each record's workflow.
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

`make run` uses a mock sign-in: pick a seeded user on `/login`. Tests use the same mode.

### Real SSO (OpenID Connect via Keycloak)
Needs Docker. Keycloak stands in for the client's identity provider (Entra ID or Okta); it needs no Azure tenant.

```bash
make sso       # starts Keycloak on :8080 with the realm in sso/realm.json
make run-sso   # http://localhost:8000, signs in through Keycloak
```

Sign in as any user below with password `demo`. Each Keycloak **group** grants the app role of the same name. On each sign-in the app syncs the user's roles from the ID token's `groups` claim and audits any change, so moving someone between groups in the Keycloak admin console (http://localhost:8080, `admin`/`admin`) changes their access on their next sign-in. MFA is a Keycloak setting (Authentication → Required actions → Configure OTP). Switching to Entra ID means changing `OIDC_ISSUER`, `OIDC_CLIENT_ID` and `OIDC_CLIENT_SECRET`, plus a groups claim on the app registration. The credentials in `sso/realm.json` and the `Makefile` are local demo values only.

Both modes seed about 50 refunds, 40 KYC cases and 13 flags of fake data (Faker, fixed seed) across every status. Set `FAKE_DATA=0` for only the hand-written examples.

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
Each step maps to a demo moment in `docs/PITCH.md`. [`docs/LOOM_FEATURE_GUIDE.md`](docs/LOOM_FEATURE_GUIDE.md) has the same features as a table, with the Power Apps equivalent, exact clicks and one line to say for each.

Run `make sso && make run-sso` and sign in with password `demo`. "Switch to X" means sign out and sign in as X. With `make run`, use the user dropdown in the header instead.

**Pillar 1: governance is built once and every tool inherits it (≈40s)**
1. Sign in as **alice** (support agent). On the home page, the tools she can't use are greyed out as "No access". Open Refunds: she can request a refund, but she can't approve one or reveal a bank account. The left menu only lists the tools her role can open. Optional: in the Keycloak admin console (http://localhost:8080, `admin`/`admin`), select realm **internal-tools** → Users → alice → Groups → **Join group** → `auditor`. When she signs in again, Audit log appears in her menu, and the audit log records her roles before → after.
2. Switch to **bob** (approver) and open refund `TXN-10412`. The bank account shows as `••••2606`. Click **Reveal**: you must give a reason, and the full value appears.
3. Switch to **ivan** (auditor) and open **Audit log** (`/audit`). The `reveal` event shows who revealed the value, when and why. Audit rows can't be edited or deleted, because database triggers reject `UPDATE` and `DELETE` on `audit_events`.
4. Change one masking rule. In `core/masking.py`, change `"refunds.bank_account"` from `mask=last4` to `mask=redact_all` and save. `make run` uses `--reload`, so the server restarts. Every refunds table and detail page now shows `••••••`. The database survives the reload, but the in-memory mock provider is reset. `tests/core/test_masking.py::test_changing_one_policy_changes_every_page` proves the same thing.

**Pillar 2: custom logic beyond the building blocks, with tests (≈40s)**

5. Self-approval: sign in as **admin**, request a refund, then try to approve it. The request is blocked: "You can't approve your own request (separation of duties)".
6. Two approvers over $1,000: as **bob**, approve `TXN-10388` ($2,400). It stays at 1 of 2 approvals. Bob can't approve it a second time. When **carol** approves, it moves to `APPROVED`.
7. Payment timeout without a double payment: as **bob**, open `TXN-10412` and select **timeout_after_accept** and click **Set mode**, then click **Execute payment**. The provider took the money but its response was lost, so the status is `UNKNOWN`, not `FAILED`, and the stage bar turns orange. Click **Reconcile with provider**. The platform looks up the payment by idempotency key, and the status becomes `SUCCEEDED`. If you click **Execute payment** again instead of reconciling, the same key is reused; `test_retry_never_pays_twice` checks that the provider was paid once (the mock has no ledger page).
8. Run `make test`. Each rule has a named test: `test_requester_cannot_approve_own_refund`, `test_retry_never_pays_twice` and the others. CI runs the same suite on every PR.

**Pillar 3: the tool factory (≈40s)**

9. Show `docs/FACTORY_RESULTS.md`. Two fresh sessions ran in parallel, and each was given only one paragraph. The table records elapsed time, PR links, which controls were inherited without being asked for, and what review had to fix.
10. Open **KYC queue** as **dave** (analyst). The government ID and date of birth are masked. There's no Reveal button until dave **claims** the case; then revealing needs a reason and is audited. Open **Feature flags** as **frank** (engineer), toggle a staging flag, then try production: frank gets no production controls. Switch to **grace** (release manager) to change production, then show the change history and one-click **Roll back to this**. Both behaviours came from review decisions recorded in `docs/FACTORY_RESULTS.md`.

## Architecture
```
app.py                 app factory: mounts core routers, discovers tools/*/router.py, creates tables, seeds
seed.py                users/roles + demo data per tool (seed_<tool>) + bulk fake data (seed_fake, Faker)
docker-compose.yml     local Keycloak (OIDC identity provider); realm, groups and users in sso/realm.json
core/
  db.py                engine/session, VersionedMixin (id, version, created_at, updated_at)
  auth.py              CurrentUser, require_role (route) / ensure_role (service); mock login when SSO is off
  sso.py               OIDC login/callback/logout (Authlib); creates/updates users and roles from IdP groups
  audit.py             append-only AuditEvent, record() in the caller's transaction, /audit queries
  masking.py           FIELD_POLICIES["<table>.<column>"], mask(), audited reveal endpoint
  concurrency.py       update_versioned(): expected-version check -> 409 StaleWrite
  workflow.py          StateMachine, ApprovalPolicy (no self-approval, N distinct approvers)
  integrations.py      adapter registry for external systems (mocked locally and in tests)
  registry.py          register_tool() + home-page launcher filtered by role
  errors.py, ui.py     typed errors -> friendly pages with the right status; Jinja + shared macros
  templates/           base (header + left menu), macros (data_table, detail, masked_field, action_form, audit_trail, stage_bar), audit
tools/<name>/          models.py, service.py, router.py, templates/, tests/ (+ adapter mock if needed)
```

Each request goes through these steps. The route's `require_role` dependency checks the role. Then a service function runs `ensure_role`, checks the business rules and validates the state transition. It writes with `update_versioned` and `audit.record` in the same transaction, then commits. Templates use the shared macros, which apply `FIELD_POLICIES`, so a tool can't render a protected field unmasked by accident.

Stack: Python 3.11, FastAPI, SQLAlchemy 2.0, SQLite (the schema is Postgres-compatible), Jinja2, HTMX, Pico.css with a Fluent-style shell (header, left menu, stage bar), Authlib for OIDC and Faker for demo data. There is no frontend build step. Tests use pytest, linting uses Ruff, and CI runs on GitHub Actions.

## Known gaps
This is a prototype, not a production platform.
- **Identity:** OIDC sign-in and group-to-role sync work against a local Keycloak, not the client's Entra ID. Roles sync only at sign-in, so removing someone from a group takes effect at their next sign-in or when the 8-hour session expires. There's no SCIM deprovisioning or Conditional Access, and MFA is configured in the IdP, not enforced by the app. `make run` and the tests still use the mock user picker.
- **Data:** it uses SQLite with `create_all`. There's no Postgres, no migrations (Alembic) and no backups. Append-only audit is enforced by SQLite triggers. Postgres would need equivalent triggers or grants, and that isn't built.
- **Integrations are mocks.** The payment provider and the flag service live in memory and reset when the app restarts (including the `--reload` in demo step 4), so flag pages can say SYNCED while the mock service is empty until the next push.
- **Masking:** a policy change is a code change and a deploy, not an admin setting. A reveal returns the raw value to the browser, and there's no rate limit or approval step for reveals.
- **No equivalent** of DLP policies, managed environments, deployment, monitoring or alerting. It hasn't had a pen test or a vendor security review. `docs/EVALUATION.md` sizes this work.
- **Governance relies on discipline.** Controls are inherited only if each tool follows `AGENTS.md`. Review and the required rule tests are the control point, as `docs/FACTORY_RESULTS.md` shows. Branch protection and required reviewers aren't configured in this repo.
- Out of scope by design: a drag-and-drop builder, pixel polish and mobile.
