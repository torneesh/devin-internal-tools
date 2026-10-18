# Key decisions: explained and ranked (raw material for the one-pager)

Score = value to the storyline (1–10): how much the decision shows *judgment* to a reviewer, not how much code it took.
Grouped by stage. A suggested one-page cut is at the bottom.

## A. Framing

**A1. Answer "can we build unknown future tools repeatedly, with governance?", not "can we clone 3 apps?"** **10/10**
- *Why:* the three apps are already paid for and working. The purchase decision is the 10+ tools nobody has specified. Cloning three apps proves Devin can write CRUD, which nobody doubts.
- *Trade-off:* the demo is less tailored to their current apps; I accepted that because the question is about future tools.
- *Shows:* scoping to the decision, not the brief's surface. (I first anchored on KYC/refund specifics and corrected course.)

**A2. Power Apps' value is speed × governance plus a managed platform, not drag-and-drop.** **9/10**
- *Why:* for a 60-engineer team, UI building isn't the bottleneck. What Power Apps gives them for free is sign-in, roles, field masking, audit, DLP, environments, Microsoft hosting and certifications, and ops staff editing simple apps. The fair comparison is "can a code platform give every tool that by default?"
- *Trade-off:* this sets a higher bar for the build option. Intended: it makes the comparison honest.

**A3. Verify claims against Microsoft's docs before building on them.** **9/10**
- *Why:* three findings changed the answer:
  - **$250K ≈ 1,000 Premium users, and Premium covers unlimited apps.** New tools don't raise the licence; users do. That kills the obvious "10 more apps = more licence" argument.
  - Test Engine is deprecated, and delegation limits can silently return incomplete results. Both are real ceilings.
  - Git integration is GA (generally available), so "no source control" was not a fair criticism. I dropped it.
- *Shows:* I let evidence cut against my own side.

**A4. Considered a Hybrid (Power Apps + Devin-built code apps), then dropped it on cost.** **8/10**
- *Why:* code apps made Hybrid technically credible. The cost model showed it's the most expensive in every scenario (licence + Devin + engineering), so it's a transition state, not a destination.
- *Shows:* I widened the option space before narrowing it, and narrowed it with numbers.

**A5. Make the recommendation gated and say what flips it.** **8/10**
- *Why:* Build wins over 3 years only if the licence is above ~$185K with user growth, the next tools are mostly custom, and someone owns the platform. The fix is a cheap test first: a licence audit, a tool list, then 6 weeks of migrating flags. A confident "build" would hide how sensitive the result is.
- *Trade-off:* a less punchy answer.

**A6. Express opportunity cost in engineer-weeks, not adjectives.** **6/10**
- *Why:* "engineering time" is the strongest argument for Buy (+0.65 FTE in Y1, +0.2 FTE ongoing). Putting a number on it forced me to concede it plainly.

## B. Scope (what I built and didn't)

**B1. Build a shared platform (`core/`), not three apps.** **9/10**
- *Why:* governance only stays consistent across 13+ tools if it's built once and inherited: auth, audit, masking, locking, approvals, adapters. Every tool is a folder that imports it.
- *Trade-off:* the platform becomes critical shared code that needs an owner (~0.5 FTE in the model). This is the biggest new cost of building, and I said so.

**B2. The tool factory is the centrepiece: fresh Devin sessions, business-language prompts, no mention of controls.** **10/10**
- *Why:* it's the only part of the prototype that tests the actual claim, "tools #4–#13 are cheap *and* governed." Leaving controls out of the prompts tests whether the repo's rules make them the default.
- *Result (from PRs #2 and #3 and the review comments on them):*
  - Both used `require_role`/`ensure_role`, `update_versioned`, `audit.record` and `StateMachine` on every action, without being asked. KYC also masked **date of birth**, which the prompt never mentioned; that came from `AGENTS.md` rule 4. Each reached a green-CI PR 6 and 8 min after launch, and merged after one review round at 30 and 38 min.
  - The review found no code defects, but it found **decisions the paragraph didn't cover**:
    - KYC: any analyst could reveal any case's ID. The fix (only the analyst holding the case can reveal) needed a per-record hook the platform didn't have. The session extended `core/masking.py`, declared it under rule 8, and added a core test.
    - Flags: an engineer creating a flag pushed OFF to **production**, which bypassed the release-manager rule. The session had raised this itself; it was fixed after review.
- *Shows:* the controls are inherited by default. The remaining risk is business decisions nobody specified, not missing controls. That is why review is the control point and why the platform needs an owner (the KYC change grew `core/`).
- *Caveat:* n=2 shows the mechanism, not a success rate.

**B3. `AGENTS.md` + `_template` as the control mechanism.** **8/10**
- *Why:* one rules file serves both human engineers and Devin: service order (role → rules → change → audit → commit), mandatory `FIELD_POLICIES` for sensitive fields, and required tests per rule. That's the code equivalent of Power Apps' "governance by default."
- *Trade-off:* rules are guidance, not enforcement. CI tests and review do the enforcing. A rule-checking lint would be next.

**B4. Refunds as the single hand-built worked example.** **7/10**
- *Why:* money movement plus partial failure (timeout → UNKNOWN → reconcile → no double pay) is precisely the kind of logic that outgrows building blocks. It shows "beyond CRUD" better than any form.
- *Trade-off:* one deep example instead of three shallow ones.

**B5. Explicitly not built: real SSO, Postgres, deployment, monitoring, a visual builder, citizen development.** **7/10**
- *Why:* these are well understood (SSO, Postgres, deploy) or not decision-relevant within a ~2h proof of concept. Citizen development is named as a real capability lost, not hand-waved.
- *Shows:* time-boxing; and honesty about the one thing Build can't replace.

## C. Architecture

**C1. Idempotency key persisted *before* calling the payment provider; UNKNOWN state plus reconcile.** **7/10**
- *Why:* a timeout after the provider accepted is the classic double-refund bug. Marking it "failed" invites a retry that pays twice. Persisting the key first and reconciling is the only safe design.
- *Trade-off:* more states and a manual reconcile step.

**C2. Business rules in a service layer that takes `(db, user, …)`; audit written in the same transaction.** **6/10**
- *Why:* rules hold for every caller, not just the UI, and a change can't commit without its audit record. The audit table is append-only at the DB level (SQLite triggers; REVOKE in Postgres).
- *Trade-off:* boilerplate per tool, absorbed by the template.

**C3. One central masking policy, rendered through one macro, with audited "reveal with reason."** **6/10**
- *Why:* changing one entry changes every tool. Audit stores masked values. This is what KYC extended, which is proof the extension point works.
- *Trade-off:* masking happens at render time. Production should also mask in the API layer and the logs.

**C4. Named business-rule tests + CI on every PR.** **6/10**
- *Why:* it turns "trust the AI" into "the rule `test_retry_never_pays_twice` passes." It's the direct counter to Power Apps' deprecated Test Engine.

**C5. Integrations behind adapters, with mocks in each tool folder.** **5/10**
- *Why:* a demo needs no credentials, tests can inject failures, and production swaps in the real client by name.

**C6. Python + FastAPI + server-rendered Jinja/HTMX, no JS build.** **4/10**
- *Why:* one language, easy to debug, fast for Devin to work in. Internal tools don't need a rich client. *Trade-off:* a plainer UI than canvas apps.

**C7. Optimistic locking (version column → 409 on stale write).** **4/10**
- *Why:* two reviewers on one case can't silently overwrite each other, and it needs no locks. *Trade-off:* the user reloads and redoes the change.

**C8. Mocked SSO behind an OIDC seam.** **4/10**
- *Why:* everything depends only on `current_user` / `require_role`, so wiring in Entra or Okta later is one function.

**C9. Cost model as editable code.** **5/10**
- *Why:* the VP can change any assumption and re-run it, which matters because the answer is sensitive to assumptions.

**C10. SQLite locally.** **2/10.** Zero setup for reviewers; the SQL is kept portable to Postgres.

## Suggested one-page cut
1. **Framing** (A1 + A2): the decision is about future tools; the value is speed × governance.
2. **Evidence changed my mind** (A3 + A4): $250K ≈ 1,000 users with unlimited apps; Hybrid dropped on cost.
3. **What I built and why** (B1 + B2 + B3): a platform plus a rules file, tested by fresh sessions. Include the KYC core extension as the honest result.
4. **One architecture example** (C1 or C2): one concrete fintech-correctness decision, not a list of all of them.
5. **What I didn't build** (B5) and **why the recommendation is gated** (A5).
6. **Uncertainties:** the licence breakdown, the next-10 mix, platform ownership, and that n=2 shows the mechanism, not a success rate.
