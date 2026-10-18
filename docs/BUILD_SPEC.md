# Build Spec: Internal Tools Platform (Devin-built Power Apps alternative)

Read first: `docs/PITCH.md` (the argument this build supports) and `docs/PRODUCT_BRIEF.md`.
**Hard cap: 2 hours from "go".** Log timestamps in `BUILD_LOG.md`. Scope is set by the pitch; anything not listed here doesn't get built.

## 1. What we're replicating: Power Apps capabilities ranked for a fintech eng team building many tools

| Rank | Power Apps capability | Why it matters to this team | Prototype treatment |
|---|---|---|---|
| 1 | **Identity & access** (Entra SSO, security roles) | Every tool touches customer data or prod | **Build:** mock SSO (user switcher), roles, `require_role`. OIDC seam documented |
| 2 | **Field-level protection** (column security, masking) | PII and bank details everywhere | **Build:** central masking policy, audited "reveal" with a reason |
| 3 | **Audit trail** (Dataverse auditing) | Regulators, SOC2, incident forensics | **Build:** append-only audit log, same DB transaction as the change, viewer page |
| 4 | **Approvals / workflow** (Power Automate approvals) | Money and prod changes need sign-off | **Build:** state machine + approval helper with separation-of-duties rules |
| 5 | **Speed to build a new tool** (canvas/model-driven, Copilot) | 10+ tools planned; this is the core value | **Build:** shared UI components + tool template + `AGENTS.md`; proven by 2 fresh Devin sessions |
| 6 | **Connectors** to systems | Their systems are their own APIs | **Build:** integration-adapter pattern with mock adapters (payments, flag service) |
| 7 | **Safe concurrent updates** (Dataverse optimistic concurrency) | Two people acting on one record | **Build:** version column, stale write → 409 |
| 8 | **Environments & ALM** (pipelines, Git) | Controlled releases | **Partial:** CI on every PR; dev/prod promotion documented |
| 9 | Monitoring (Live Monitor) | Know when a tool breaks | **Doc only** |
| 10 | Citizen development, mobile app, managed hosting | | **Gap:** called out honestly in the pitch |

## 2. Architecture

**Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, SQLite (Postgres-compatible SQL), Jinja2 + HTMX + Pico.css (CDN, no JS build), pytest, ruff. Dependencies in `requirements.txt`.
**Why:** one language, easy to debug, no frontend toolchain. Server-rendered pages are enough for internal tools.
**Run:** `make setup && make run` (port 8000), `make test`, `make lint`. Seed data loads on startup.

```
core/                    # the shared platform: every tool imports from here (not "platform": that name shadows the stdlib)
  db.py                  # engine, session, Base, VersionedMixin (id, version, created_at, updated_at)
  auth.py                # mock SSO: session cookie holds user; current_user dep; require_role(*roles); /login user picker
  audit.py               # AuditEvent model; record(db, actor, action, entity, entity_id, before, after, reason)
                         # SQLite triggers block UPDATE/DELETE on audit_events (append-only)
  masking.py             # FIELD_POLICIES = {"refund.bank_account": Policy(mask=last4, reveal_roles=...)}
                         # mask(entity, field, value, user); reveal(...) requires a reason and writes an audit event
  concurrency.py         # update_versioned(db, obj, expected_version, **changes) -> raises StaleWrite (409)
  workflow.py            # StateMachine(transitions); Approvals: no self-approval, N distinct approvers above a threshold
  integrations.py        # Adapter Protocol + registry; mocks live with their tool
  registry.py            # register_tool(name, path, roles, description) -> launcher home page
  errors.py              # PermissionDenied / StaleWrite / InvalidTransition -> friendly HTML + correct status
  templates/             # base.html (nav, current user + switcher, flash), macros: data_table, detail, masked_field, action_form, audit_trail
tools/
  refunds/               # worked example, built in this session (section 3)
  kyc/                   # built by fresh Devin session A
  flags/                 # built by fresh Devin session B
  _template/             # copy-me skeleton: router.py, models.py, service.py, templates/, tests/
app.py                   # FastAPI app; auto-includes tools/*/router.py; /audit viewer (auditor role)
seed.py                  # users, roles, demo data
tests/core/              # platform tests
AGENTS.md                # rules every tool must follow (section 4)
.github/workflows/ci.yml # ruff + pytest on PRs
```

**Seed users** (switch with one click; names are the demo cast):

| User | Role |
|---|---|
| alice | support_agent |
| bob, carol | refund_approver |
| dave | kyc_analyst |
| erin | kyc_supervisor |
| frank | engineer |
| grace | release_manager |
| ivan | auditor |
| admin | all roles |

**Key design rules:**
- Business logic lives in `service.py`, not in routes. Services take `(db, user, ...)`, enforce permissions and rules, and write audit in the same transaction.
- Every mutation goes through `update_versioned`; every write is audited.
- Masking is applied at render via the `masked_field` macro, driven by the central policy. Changing one policy line changes every tool.

## 3. Refunds worked example (built in this session)

**Model:** `Refund`:
- Fields: `txn_id`, `customer_name`, `bank_account` (masked), `amount_cents`, `reason`, `status`, `requested_by`, `idempotency_key`, `provider_ref`, `version`
- Plus `RefundApproval` (`refund_id`, `approver`, `at`)

**States:** `REQUESTED → APPROVED → SUBMITTED → SUCCEEDED | FAILED | UNKNOWN`. Also `REQUESTED → REJECTED` and `UNKNOWN → SUCCEEDED | FAILED` (via reconcile).

**Rules:**
- Only `support_agent` can request.
- Only `refund_approver` can approve, and **never the requester**.
- Amount > $1,000 needs **2 distinct approvers**.
- Only APPROVED can be executed.

**Execution (the key demo):**
- On first execute, generate and persist `idempotency_key` **before** calling the provider.
- `MockPaymentProvider` is keyed by idempotency key; a repeat call returns the original result and never pays twice.
- Modes are set per refund via a demo dropdown: `ok`, `fail`, `timeout_after_accept` (records the payment, then raises a timeout).
- A timeout produces status `UNKNOWN`, not FAILED.
- **Reconcile** asks the provider by key and sets SUCCEEDED or FAILED. Retrying execute on UNKNOWN goes via the same key, so there's no duplicate payment.

**Pages:** list (filter by status), new request form, detail (masked bank account + reveal, approvals, actions, audit trail), and the demo provider-mode dropdown.

**Tests (named after the rule):**
- `test_requester_cannot_approve_own_refund`
- `test_over_threshold_requires_two_distinct_approvers`
- `test_cannot_execute_unapproved`
- `test_timeout_marks_unknown_not_failed`
- `test_reconcile_resolves_unknown`
- `test_retry_never_pays_twice`
- `test_stale_update_rejected`
- `test_every_mutation_audited`
- `test_bank_account_masked_and_reveal_audited`
- `test_wrong_role_forbidden`

## 4. `AGENTS.md` (write this before launching the child sessions)
Short, imperative, and the single source of truth for a new tool:
1. Copy `tools/_template` to `tools/<name>`. Register it with `register_tool`.
2. Use `require_role` on every route. Add any new roles to `seed.py`.
3. Every model uses `VersionedMixin`. Every mutation goes through `update_versioned` and `audit.record` in a service function.
4. Sensitive fields (IDs, bank details, emails, phone, addresses, secrets) **must** have a `FIELD_POLICIES` entry and render via `masked_field`.
5. Status changes go through a `StateMachine`. Approvals use the `workflow` helpers (no self-approval).
6. External systems go behind an adapter in `integrations.py` with a mock for local and tests.
7. Tests are required: a permission test per action, a test per business rule, and an audit test. `make test` and `make lint` must pass.
8. Don't change `core/` without saying so explicitly in the PR description.
9. The PR description lists roles, rules, sensitive fields and how to demo.

## 5. Fresh-session prompts (the "tool factory" demo)
Launch both **in parallel** as child Devin sessions on this repo after `main` has the platform, refunds, `AGENTS.md` and CI. The prompts deliberately describe **business needs only**: no mention of audit, masking, versioning or the platform. The test is whether the controls get inherited.

**A: KYC review queue**
> "Build a KYC review queue tool in this repo. Compliance analysts work through customer verification cases: each case has the customer's name, date of birth, government ID number, country and uploaded-document status. Analysts claim a case, then approve or reject it with a reason, or escalate it to a supervisor. Only supervisors can resolve escalated cases. Analysts shouldn't see full government ID numbers unless they have a reason. Open a PR when done."

**B: Feature-flag admin**
> "Build a feature-flag admin tool in this repo. Engineers can create flags and toggle them or change rollout percentage in staging. Changing a flag in production is restricted to release managers. Every flag needs a visible change history and one-click rollback to a previous value. Flag changes should be pushed to our flag service (mock it for now). Open a PR when done."

Record for each: start/end time, PR link, whether controls were inherited unprompted (audit / roles / masking / versioning / tests), and what needed fixing in review. **That table goes into the pitch, warts and all.**

## 6. Time plan and definition of done
| Block | Budget | Done when |
|---|---|---|
| Platform core + templates + seed + core tests | 45 min | Login switch works, audit is append-only, masking + reveal work, 409 on stale write |
| `AGENTS.md` + `_template` | 10 min | Template tool passes lint/tests |
| Refunds + tests + CI | 30 min | All section-3 tests green in GitHub Actions |
| Launch A + B in parallel | 5 min | Both sessions running |
| (while they run) README + audit page + masking-policy demo | 15 min | README covers run, demo script, architecture, gaps |
| Review/merge A + B, fill results table | 15 min | Both merged or documented as-is |

**Cut line:** platform + refunds + one factory-built tool is the minimum. If a child session overruns, record its state honestly. Don't fix it by hand to make it look better.

**Out of scope:** real SSO, Postgres, deployment, monitoring, drag-and-drop builder, pixel polish, mobile.
