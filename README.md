# devin-internal-tools

A prototype internal-tools platform, built with Devin, as an alternative to Microsoft Power Apps for a fintech engineering team.

**The question it answers:** the team pays about $250K a year for Power Apps, and plans to build 10+ more internal tools. Can Devin build those tools on a small shared platform, with the same governance Power Apps gives them (sign-in, roles, protected data, audit, approvals), plus custom logic Power Apps' building blocks struggle with?

## What's in it

| Part | What it is |
|---|---|
| **`core/`** | The shared platform every tool inherits: OIDC sign-in with identity-provider groups mapped to roles, role checks, field masking with audited reveal, an append-only audit log, approval rules, state machines, optimistic locking, adapters for external systems, and a shared UI shell (header, role-filtered left menu, workflow stage bar). |
| **`tools/refunds/`** | The hand-built worked example: two approvers above $1,000, no self-approval, and a payment-provider timeout handled without paying twice. |
| **`tools/kyc/`**, **`tools/flags/`** | A KYC review queue and a feature-flag admin, each built by a fresh Devin session from a one-paragraph business request that didn't mention any controls. Results: [`docs/FACTORY_RESULTS.md`](docs/FACTORY_RESULTS.md). |
| **`tools/_template/`**, **[`AGENTS.md`](AGENTS.md)** | The starting point and the rules for every new tool, written for engineers and Devin alike. |
| **[`docs/evaluation/`](docs/evaluation/)** | The Power Apps vs Build analysis: product brief, evaluation, cost model (with its script), compliance, success metrics and research. |

## Run it

Requires Python 3.11.

```bash
make setup   # creates .venv and installs requirements.txt
make run     # http://localhost:8000, mock sign-in: pick a user on /login
make test    # pytest: platform tests plus each tool's rule tests
make lint    # ruff check + ruff format --check (same as CI)
```

Every start deletes `app.db` and reseeds it, so the demo always begins from the same state: about 50 refunds, 40 KYC cases and 13 flags of fake data (Faker, fixed seed) plus the hand-written examples used below. Set `FAKE_DATA=0` for the hand-written examples only.

### With real SSO (OpenID Connect via Keycloak)

Needs Docker. Keycloak stands in for the client's identity provider (Entra ID or Okta), so no Azure tenant is needed.

```bash
make sso       # starts Keycloak on :8080 with the realm in sso/realm.json
make run-sso   # http://localhost:8000, signs in through Keycloak
```

Every user's password is `demo`. Each Keycloak **group** grants the app role of the same name. Roles sync from the ID token's `groups` claim at each sign-in, and any change is audited. The Keycloak admin console is at http://localhost:8080 (`admin` / `admin`). Switching to Entra ID means setting `OIDC_ISSUER`, `OIDC_CLIENT_ID` and `OIDC_CLIENT_SECRET` and adding a groups claim to the app registration; no tool code changes. All credentials in this repo are local demo values.

| User | Role | Use it to show |
|---|---|---|
| alice | support_agent | Requests refunds only; the menu hides everything else |
| bob, carol | refund_approver | Reveal bank details, approve refunds (two approvers needed above $1,000) |
| dave, heidi | kyc_analyst | Claim and decide KYC cases |
| erin | kyc_supervisor | Resolve escalated KYC cases |
| frank | engineer | Change flags in staging, not production |
| grace | release_manager | Change flags in production |
| ivan | auditor | Read-only audit log |
| admin | every role | Self-approval check, quick tour |

## Demo (about 2 minutes)

"Switch to X" means sign out and sign in as X. With `make run`, use the user picker instead.

**Governance every tool inherits**
1. Sign in as **alice**. Tools she can't use show as "No access", and the left menu lists only Refunds.
2. Switch to **bob** and open refund `TXN-10388`. The bank account is masked (`••••3000`). **Reveal** asks for a reason, then shows the value.
3. Switch to **ivan** and open **Audit log**. The reveal is there: who, when and why. Audit rows can't be edited or deleted (database triggers block it).

**Custom logic beyond the building blocks**

4. As **admin**, request a refund and try to approve it: blocked ("You can't approve your own request").
5. As **bob**, approve `TXN-10388` ($2,400). It stays at 1 of 2 approvals. When **carol** approves, it becomes `APPROVED`.
6. As **bob**, open `TXN-10412`, choose **timeout_after_accept**, click **Set mode**, then **Execute payment**. The provider took the money but its reply was lost, so the refund is `UNKNOWN` (orange stage bar), not `FAILED`. Click **Reconcile with provider**: the app looks the payment up by its idempotency key, and the refund becomes `SUCCEEDED` (stage bar: Paid). Retrying instead reuses the same key, so the customer is never paid twice (`test_retry_never_pays_twice`).

**New tools get it for free**

7. As **dave**, open **KYC queue**. The government ID and date of birth are masked, and there's no Reveal until dave claims the case.
8. As **frank**, open **Feature flags**. He can change staging but has no production controls. As **grace**, change production, then use **Roll back to this** in the change history.

Each business rule has a named test, e.g. `test_requester_cannot_approve_own_refund`. Run `make test` to see them.

## How it works

```
app.py                 app factory: mounts core routers, discovers tools/*/router.py, creates tables, seeds
seed.py                users and roles, demo data per tool (seed_<tool>), bulk fake data (seed_fake)
docker-compose.yml     local Keycloak; realm, groups and users in sso/realm.json
core/
  auth.py              current_user, require_role (routes) / ensure_role (services); mock login when SSO is off
  sso.py               OIDC login/callback/logout; creates users and syncs roles from IdP groups
  audit.py             append-only audit log, written in the caller's transaction
  masking.py           FIELD_POLICIES["<table>.<column>"]: mask functions, who may reveal, audited reveal
  concurrency.py       update_versioned(): stale writes return 409
  workflow.py          StateMachine, ApprovalPolicy (no self-approval, N distinct approvers)
  integrations.py      adapter registry for external systems (mocked locally and in tests)
  registry.py          register_tool(): adds a tool to the home page and the role-filtered menu
  db.py, errors.py, ui.py, templates/   models base, typed errors, shared page shell and macros
tools/<name>/          models.py, service.py, router.py, templates/, tests/ (+ adapter mock if needed)
```

Every request follows the same path. The route checks the role (`require_role`). The service function checks it again (`ensure_role`), applies the business rules and the allowed state transition, saves the change with `update_versioned`, and writes the audit record in the same database transaction. Pages render through shared macros that apply the masking policies, so a tool can't show a protected field unmasked by accident.

To add a tool, copy `tools/_template` and follow [`AGENTS.md`](AGENTS.md).

**Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, SQLite (Postgres-compatible schema), Jinja2 + HTMX, Pico.css, Authlib (OIDC), Faker. No frontend build step. pytest and Ruff run in GitHub Actions on every PR.

## Known gaps

This is a prototype, not a production platform.
- **Identity:** works against a local Keycloak, not the client's Entra ID. Roles sync only at sign-in, so a removed role lasts until the next sign-in or the 8-hour session expiry. No SCIM deprovisioning or Conditional Access; MFA is configured in the identity provider.
- **Data:** SQLite with no migrations, backups or encryption at rest. Production needs Postgres, Alembic and audit-log protection equivalent to the SQLite triggers.
- **Integrations are mocks.** The payment provider and flag service live in memory and reset on restart.
- **Masking:** a policy change is a code change and a deploy. There's no rate limit or approval step on reveals.
- **Operations:** no deployment, monitoring, alerting, DLP or managed environments. No pen test or vendor security review yet.
- **Compliance:** no retention and deletion schedule (AML retention vs GDPR erasure), data-subject export or SIEM feed. See [`docs/evaluation/COMPLIANCE.md`](docs/evaluation/COMPLIANCE.md).
- **Governance relies on review.** Tools inherit controls by following `AGENTS.md`; review and the required rule tests are the check. Branch protection and required reviewers aren't configured in this repo.
- **Not built by design:** a drag-and-drop builder, citizen development, mobile apps and offline mode.
