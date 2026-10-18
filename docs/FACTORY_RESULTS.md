# Factory results: two tools from one paragraph each

Two fresh Devin sessions were launched in parallel from this repo's `main` at 14:26:35 UTC on 2026-10-18, after [PR #1](https://github.com/torneesh/devin-internal-tools/pull/1) (platform, refunds, `AGENTS.md`, CI) was merged at 14:26:29. Each got **only** the paragraph from `docs/BUILD_SPEC.md` §5, word for word: no mention of audit, masking, versioning, tests or the platform. The parent session reviewed their PRs as a human reviewer would (reading the diff, running tests and lint, and making requests as each role). It didn't push fixes to their branches. The product owner decided the open questions.

## Results

| | A: KYC review queue | B: Feature-flag admin |
|---|---|---|
| Session | [339f1fd6](https://app.devin.ai/sessions/339f1fd6fc604a74b30433597b06c457) | [db1aceb4](https://app.devin.ai/sessions/db1aceb4645f4792b468d8be024b9821) |
| Start (UTC) | 14:26:35 | 14:26:36 |
| PR opened, CI green | 14:32:40 (**6 min**) | 14:34:35 (**8 min**) |
| Merged after review | 15:04 (38 min) | 14:56 (30 min) |
| PR | [#2](https://github.com/torneesh/devin-internal-tools/pull/2) | [#3](https://github.com/torneesh/devin-internal-tools/pull/3) |
| New tests at first PR | 26 (59 total) | 23 (56 total) |
| New tests at merge | 29 (90 total with both tools) | 27 |
| Roles inherited unprompted | **Yes.** `require_role` on every route, `ensure_role` in every service function. Used the seeded `kyc_analyst` / `kyc_supervisor` roles and added a second analyst user. Supervisor-only resolution is enforced in the service. | **Yes.** Production restricted to `release_manager` in the service layer, not only in the UI. Auditor is read-only. |
| Audit inherited unprompted | **Yes.** Every mutation, with reasons. Test `test_every_mutation_audited`. | **Yes.** Every mutation, including push results and the demo outage toggle. Test `test_every_mutation_audited`. |
| Masking inherited unprompted | **Yes.** `FIELD_POLICIES` entries for the government ID **and** the date of birth (the prompt only mentioned the ID; the DOB came from `AGENTS.md` rule 4). Reveal needs a reason and is audited. No raw values in list, detail, flash or `/audit` pages (tested). | **Correctly none.** No sensitive fields. The PR says so and why. |
| Versioning inherited unprompted | **Yes.** `VersionedMixin` + `update_versioned`, with a stale-write test. A claim race returns a 409. | **Yes.** On flags and per-environment states, with stale-write tests at the service and route level. |
| Other platform pieces | `StateMachine` for case status, `ApprovalPolicy` for the self-resolve rule. | `StateMachine` for sync status. Flag service behind an `integrations` adapter with an in-memory mock, full-state pushes with revisions, FAILED + retry, late pushes ignored. |
| `core/` changes | `FIELD_POLICIES` entries plus a 2-line `year_only` mask (declared in the PR). After review: a per-record `can_reveal` hook on `Policy` (declared). | None. |
| Code defects found in review | None. | None. |
| Needed fixing in review | 2 decisions: keep the document rule; restrict reveal to the claimant (a `core/masking` hook). Fixed in one round, 2 min. | 1 change: don't push production on create (the session had flagged it). Fixed in one round, 15 min. |

## What review had to fix (warts and all)

Round 1 (14:36 to 14:40): the parent reviewed both PRs and posted review comments. Both sessions had flagged their own open questions, which were passed to the product owner. The owner's decisions:

1. **KYC: keep the unrequested rule** that a case can only be approved once documents are `UPLOADED`. The session added it on its own and labelled it an assumption. It stays, as a business rule.
2. **KYC: restrict reveal to the claimant.** As built, any analyst could reveal the ID on any case after giving a reason. The owner wants reveal limited to the analyst holding the case, with supervisors exempt. This needs a small `core/masking.py` hook (a per-record `can_reveal` check on `Policy`), which the session had deliberately avoided to stay out of `core/`.
3. **Flags: don't push production on create.** Creating a flag (an engineer action) pushed OFF/0% to production. That conflicts with "production changes are restricted to release managers", and it would overwrite a live value if the flag service already knew the key. The session had flagged this itself. The fix: production stays unpushed until a release manager's first change.

Round 2 (feedback sent 14:40):
- **Flags:** fix pushed at 14:55 ([ef3a4ea](https://github.com/torneesh/devin-internal-tools/commit/ef3a4ea)). Production starts `NOT_SET`, nothing is pushed on create, a release manager's first change is the first production push, retry is refused while unset, and the audit event records the first value as changed from "not set". Four new tests (60 total). The session also recorded its own browser test. One small follow-on decision surfaced: an explicit OFF/0% is accepted as the first production value because "not set" and OFF differ. Accepted in review. **Merged 14:56** (about 30 minutes from launch, including the review round and the owner's decision).
- **KYC:** fix pushed at 14:42 ([aca3400](https://github.com/torneesh/devin-internal-tools/commit/aca3400)), 2 minutes after the feedback. `Policy` got an optional per-record `can_reveal(db, user, obj)` hook, run after the role check; policies without it (refunds) are unchanged. A refused reveal is a 403 with no audit event, and the Reveal button is hidden by the same check. One core test plus two KYC tests. The session then ran its own browser test, merged `main` (one `seed.py` conflict, resolved) and re-ran everything with both tools mounted: 90 tests. Review nit, left as a comment and not blocking: `core/masking.py` now lazy-imports the KYC rule, so core knows about one tool; a `register_policy(...)` call from the tool would be cleaner. **Merged 15:04** (about 38 minutes from launch, including two product decisions and a `core/` change).

## Read-out for the pitch
- Both sessions inherited every control in `AGENTS.md` without being told, and both opened PRs with green CI in under 10 minutes.
- Neither needed a code fix. What review changed were **product decisions** the sessions had surfaced themselves (one of them also a requirement reading). Each fix landed in one round, in 2 and 15 minutes. That's the control point the pitch describes: an engineer reviewing a PR, with the rule tests and the audit trail doing the mechanical part.
- The one gap the platform itself showed: masking policies were role-based only. A per-record reveal rule needed a `core/` change. That's a platform improvement that every later tool inherits, which is the point of having one.
