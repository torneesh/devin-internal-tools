# Product Brief: Internal Tools Platform (Power Apps alternative)

## Why we're building this
The client pays ~$250K/yr for Power Apps, runs 3 internal apps on it (KYC review queue, refunds dashboard, feature-flag admin), and plans 10+ more. The VP of Engineering wants to know if engineers using Devin can build these tools in-house instead.

The prototype has one job: **show whether a Devin-built platform can deliver the value Power Apps gives this client today, and say plainly where it can't.** It is not a feature-for-feature clone. The client's value isn't the drag-and-drop UI. It's the controls around sensitive data, money movement and production changes, plus making each new tool cheap to add.

## Who uses these tools (hypotheses to validate)
"60 engineers" tells us build capacity. It doesn't tell us user count or maintenance capacity. The users are probably a larger ops, finance and compliance group.

| App | Likely users | Risk profile | What matters most |
|---|---|---|---|
| KYC review queue | Compliance analysts, reviewers, supervisors | **Exposes sensitive data** | Case assignment, restricted PII/doc access, decision reasons, escalation, reviewer history, no conflicting decisions |
| Refunds dashboard | Support, finance, approvers | **Moves money** | Accurate txn data, approval thresholds, separation of duties, no duplicate refunds, execution status, reconciliation |
| Feature-flag admin | Engineers, product, on-call | **Changes prod behaviour** | Env separation, restricted prod changes, change history, validation, rollback, reliable integration with the flag service |

## Requirements, priority, and what the prototype covers
Coverage key:
- **Build**: working in the prototype, with tests
- **Partial**: working with a mock or seam where production needs more
- **Doc**: designed and written up, not built
- **Gap**: Power Apps advantage we don't replicate

| # | Capability | Pri | Power Apps today | Prototype |
|---|---|---|---|---|
| 1 | SSO / identity | P0 | Entra ID native | **Partial**: real OIDC sign-in against a local Keycloak; IdP groups → roles, synced and audited at each sign-in; 8-hour session. Moving to Entra is configuration (issuer, client ID, secret). No SCIM deprovisioning or Conditional Access |
| 2 | Role-based access (RBAC) | P0 | Security roles | **Build** |
| 3 | Separation of duties / business rules (no self-approval; refunds > threshold need a 2nd, different approver; staging access ≠ prod access) | P0 | Approvals exist; **client still defines and enforces the rules** | **Build** |
| 4 | Field-level protection (masked gov ID / bank details, audited "reveal", export limits) | P0 | Dataverse column security + masking | **Build** (mask + audited reveal); export control **Doc** |
| 5 | Audit trail (who, what, before/after, reason) | P0 | Dataverse auditing | **Build**: append-only, written in the same transaction as the change |
| 6 | Concurrency + valid state transitions (two reviewers, one case) | P0 | Optimistic concurrency available; **app must use it** | **Build**: version column (stale save → 409), explicit state machine |
| 7 | Safe money movement (one-time execution keys so a retry can't refund twice, approved → submitted → succeeded/failed/unknown, reconcile) | P0 | **Not provided**; needs deliberate design on either platform | **Build** against a mock payment provider that can time out |
| 8 | Integrations with existing systems (core DB, payments, flag service) | P1 | 1,000+ connectors; in-house systems likely need custom connectors | **Partial**: adapter interface + mocks |
| 9 | Environments + controlled releases | P1 | Dev/test/prod + deployment pipelines | **Partial**: PR review + CI tests; in-app staging/prod for flags. Promotion pipeline **Doc** |
| 10 | Recovery: release (undo a bad change) and data (restore records) | P1 | Pipelines; Dataverse backup/restore (doesn't cover external systems) | **Partial**: git revert, flag rollback, audit-based reconstruction. Postgres point-in-time recovery **Doc** |
| 11 | Operational visibility (failed/stuck actions, integration errors) | P1 | Live Monitor, flow run history; connector limits apply | **Partial**: "unknown/failed" queue surfaced in UI. Monitoring/alerting **Doc** |
| 12 | Reuse across 13+ tools (shared components, one security fix applies everywhere) | P1 | Component libraries | **Build**: shared platform module + `AGENTS.md`; proven by a fresh Devin session building the flag app |
| 13 | Ops/business staff change tools themselves without engineering | P2* | Core low-code proposition | **Gap**: every change goes through an engineer reviewing a Devin PR |
| 14 | Managed hosting, patching, Microsoft compliance attestations | P1 | Microsoft absorbs; client still owns app logic, access config, data, integrations | **Gap**: client owns hosting on their existing cloud |
| 15 | Mobile / offline | P2 | Native player app | **Gap**: responsive web only |
| 16 | Ongoing ownership (who maintains app #9 when its author leaves) | P1 | Same problem, arguably worse with citizen devs | **Doc**: ownership model, not code |

*P2 unless the VP says ops staff build or edit apps today. If they do, this becomes a P0 and weighs heavily toward buy.

**Coverage:** P0s are 6 of 7 built, 1 partial (SSO works over OIDC against a local Keycloak, not the client's Entra). P1s are 1 built, 4 partial, 2 doc/gap. P2s aren't replicated.

## The key point for the VP
Most of the hard P0 work (#3, #6, #7) is **business logic the client must design and get right on either platform**. Power Apps gives them primitives, not answers. What Power Apps really takes off their plate is #1, #13 and #14: identity plumbing, citizen development, and running and attesting the platform. The build-vs-buy question is whether owning those is cheaper than ~$250K/yr once Devin lowers the cost of building, without creating a maintenance burden across 13+ apps.

## Prototype success criteria
1. Each P0 rule has a passing test, e.g. a self-approval attempt is rejected, a stale save returns 409, and a retried refund executes once.
2. A **fresh Devin session** given only a one-paragraph request builds the feature-flag admin. It inherits auth, audit, masking and state-transition patterns via `AGENTS.md` without being told, and opens a reviewable PR. Timed.
3. Built within the 2-hour cap; elapsed time logged.
4. Runs with one command; shown in under 5 minutes.

## Non-goals
Pixel-perfect UI, a drag-and-drop builder, real SSO/payment/flag integrations, production deployment, a migration plan for existing Power Apps data.

## Open questions for the VP (these change the recommendation)
1. How many users are on the license, and is it per-user, per-app or capacity licensing? Does cost grow with ops headcount?
2. Who builds and changes the apps today: engineers, or ops/compliance staff?
3. Compliance scope: SOC2, PCI, regulator audit expectations for KYC decisions?
4. Where does the data live: Dataverse, or their own DB via connectors?
5. Existing stack: cloud, identity provider, flag service, payment provider?
6. Is there a team with capacity to own a shared internal-tools platform (~0.5 FTE ongoing)?
