# Factory results: two tools from one paragraph each

The test: can a fresh Devin session, given only a business request, build a new tool that inherits the platform's controls without being told about them?

After [PR #1](https://github.com/torneesh/devin-internal-tools/pull/1) (platform, refunds, `AGENTS.md`, CI) was merged, two fresh Devin sessions were launched in parallel on this repo. Each got **only** one of the paragraphs below, word for word. Neither mentioned audit, masking, versioning, tests or the platform. Their PRs were reviewed as a human reviewer would review them: reading the diff, running tests and lint, and trying each action as each role. The reviewer didn't push fixes to their branches. Open product questions went to the product owner.

## The prompts

**A: KYC review queue**
> "Build a KYC review queue tool in this repo. Compliance analysts work through customer verification cases: each case has the customer's name, date of birth, government ID number, country and uploaded-document status. Analysts claim a case, then approve or reject it with a reason, or escalate it to a supervisor. Only supervisors can resolve escalated cases. Analysts shouldn't see full government ID numbers unless they have a reason. Open a PR when done."

**B: Feature-flag admin**
> "Build a feature-flag admin tool in this repo. Engineers can create flags and toggle them or change rollout percentage in staging. Changing a flag in production is restricted to release managers. Every flag needs a visible change history and one-click rollback to a previous value. Flag changes should be pushed to our flag service (mock it for now). Open a PR when done."

## Results

| | A: KYC review queue | B: Feature-flag admin |
|---|---|---|
| Session | [339f1fd6](https://app.devin.ai/sessions/339f1fd6fc604a74b30433597b06c457) | [db1aceb4](https://app.devin.ai/sessions/db1aceb4645f4792b468d8be024b9821) |
| PR | [#2](https://github.com/torneesh/devin-internal-tools/pull/2) | [#3](https://github.com/torneesh/devin-internal-tools/pull/3) |
| Launch → PR open with green CI | **6 min** | **8 min** |
| Launch → merged after review | 38 min | 30 min |
| New tests at first PR / at merge | 26 / 29 | 23 / 27 |
| Roles inherited unprompted | **Yes.** `require_role` on every route, `ensure_role` in every service function. Used the seeded `kyc_analyst` / `kyc_supervisor` roles and added a second analyst user. Supervisor-only resolution is enforced in the service. | **Yes.** Production restricted to `release_manager` in the service layer, not only in the UI. Auditor is read-only. |
| Audit inherited unprompted | **Yes.** Every mutation, with reasons (`test_every_mutation_audited`). | **Yes.** Every mutation, including push results and the demo outage toggle (`test_every_mutation_audited`). |
| Masking inherited unprompted | **Yes.** `FIELD_POLICIES` entries for the government ID **and** the date of birth. The prompt only mentioned the ID; the date of birth came from `AGENTS.md` rule 4. Reveal needs a reason and is audited. No raw values on list, detail, flash or audit pages (tested). | **Correctly none.** No sensitive fields; the PR says so and why. |
| Versioning inherited unprompted | **Yes.** `VersionedMixin` + `update_versioned`, with a stale-write test. Two analysts claiming the same case get a 409. | **Yes.** On flags and per-environment states, with stale-write tests at the service and route level. |
| Other platform pieces | `StateMachine` for case status, `ApprovalPolicy` for the no-self-resolve rule. | `StateMachine` for sync status. Flag service behind an `integrations` adapter with an in-memory mock: full-state pushes with revisions, FAILED + retry, late pushes ignored. |
| `core/` changes | `FIELD_POLICIES` entries plus a 2-line `year_only` mask (declared in the PR). After review: a per-record `can_reveal` hook on `Policy` (declared). | None. |
| Code defects found in review | None. | None. |
| Changed in review | 2 product decisions (below). Fixed in one round, in 2 min. | 1 product decision (below). Fixed in one round, in 15 min. |

## What review changed

Both sessions flagged their own open questions in the PR. The product owner decided them:

1. **KYC: keep the unrequested rule** that a case can only be approved once documents are `UPLOADED`. The session added it on its own and labelled it an assumption. It stays as a business rule.
2. **KYC: restrict reveal to the claimant.** As built, any analyst could reveal the ID on any case after giving a reason. The owner wanted reveal limited to the analyst holding the case, with supervisors exempt. That needed a small `core/masking.py` hook, which the session had avoided to stay out of `core/`.
3. **Flags: don't push production on create.** Creating a flag (an engineer action) pushed OFF/0% to production. That conflicts with "production changes are restricted to release managers", and could overwrite a live value. The session had flagged this itself.

The fixes:
- **Flags** ([ef3a4ea](https://github.com/torneesh/devin-internal-tools/commit/ef3a4ea)): production starts `NOT_SET`, nothing is pushed on create, a release manager's first change is the first production push, retry is refused while unset, and the audit event records the first value as changed from "not set". Four new tests. An explicit OFF/0% is accepted as the first production value, because "not set" and OFF differ; accepted in review.
- **KYC** ([aca3400](https://github.com/torneesh/devin-internal-tools/commit/aca3400)): `Policy` got an optional per-record `can_reveal(db, user, obj)` hook, run after the role check. Policies without it (refunds) are unchanged. A refused reveal is a 403 with no audit event, and the Reveal button is hidden by the same check. One core test plus two KYC tests. The session merged `main` (one `seed.py` conflict) and re-ran everything with both tools mounted: 90 tests passing.
- Review nit, not blocking: `core/masking.py` lazy-imports the KYC rule, so core knows about one tool. A `register_policy(...)` call from the tool would be cleaner.

## What this shows
- Both sessions used every control in `AGENTS.md` without being told, and opened PRs with green CI in under 10 minutes.
- Neither needed a code fix. Review changed **business decisions the prompt didn't cover**, which the sessions had surfaced themselves. So human review stays the control point, with the rule tests and the audit trail doing the mechanical checks.
- The platform showed one gap: masking was role-based only, and a per-record reveal rule needed a `core/` change. Every later tool inherits that improvement.
- Two tools show the mechanism works. They don't establish a success rate.
