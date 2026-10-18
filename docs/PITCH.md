# VP Pitch v3: argument structure (5-minute Loom)

Audience: VP of Engineering. Technical, budget owner, will own on-call, and wary of AI hype.
**Thesis:** the decision isn't about the 3 apps they have. It's about the 10+ tools they haven't specified yet. The requirement is a **repeatable way to build any custom tool quickly, with governance built in**.
Structure: answer → what Power Apps really sells → 3 pillars, each with evidence → cost → risks → what flips it → next steps.

---

## The answer (0:00–0:30)
> "**Build with Devin, as a gated migration.** You're about to build ten-plus tools nobody has fully specified yet. Power Apps makes that fast as long as each tool fits its building blocks. Devin on a shared platform gives you the same speed and the same built-in governance, without that ceiling. The money saving is real but modest, and it depends on your licence breakdown."

## What Power Apps really sells you (0:30–1:10)
**Speed × governance, repeated across many tools:**
- **Speed:** building blocks (canvas, connectors, Dataverse, Copilot) let a small team ship a tool in days.
- **Governance:** each tool comes with Entra sign-in, roles, field masking, audit, DLP and managed environments, without anyone building them.
- **A managed platform:** Microsoft hosts and patches it; ops staff can make edits themselves.

**Where the building blocks run out:**
- Custom logic (multi-step approvals, failure handling for money movement)
- Your own APIs (custom connectors + gateway)
- Testing (Test Engine **deprecated**)
- Scale (delegation limits that **silently return wrong results**)

Each new bespoke tool raises the odds of hitting one of these.

> "So the real question is whether Devin can match the speed and governance for *any* tool, including the ones that outgrow the building blocks."

## Pillar 1: Governance is built once and every tool inherits it (1:10–1:45)
**Claim:** Sign-in, roles, field masking, audit, approvals and safe updates live in one shared platform. They're security-reviewed once and inherited by every tool, so tool #13 is as governed as tool #1.
**Evidence:**
- Switch user → see different permissions.
- Masked field → "Reveal" requires a reason → appears in the audit log.
- Change one masking rule in the platform → every tool picks it up.

**Honest caveat:** in Power Apps this is configuration you get for free; here you own it.

## Pillar 2: Beyond the building blocks: custom logic, tested (1:45–2:25)
**Claim:** When a tool needs logic the building blocks don't cover, it's ordinary code on the platform, with tests in CI.
**Evidence (refunds, chosen deliberately as their riskiest workflow: money movement, not a form):**
- No self-approval; a second approver over the threshold.
- Payment provider times out → `UNKNOWN` → reconcile → a retry **doesn't pay twice**.
- The test suite runs on screen; each rule is a named test.

The point isn't refunds specifically. It's that the next tool's odd requirement is just code, not a workaround.

## Pillar 3: The tool factory (2:25–3:05). The main demo.
**Claim:** An engineer writes a paragraph, and Devin builds the tool on the platform, following the platform rules (`AGENTS.md`). A human reviews the PR. Several tools can be built in parallel.
**Evidence:**
- **Two fresh Devin sessions run in parallel**, each given only one paragraph:
  - **KYC review queue:** PII-heavy, case workflow.
  - **Feature-flag admin:** config, prod-restricted, rollback.
- Both reuse sign-in, roles, audit and masking **without being told**. Both open PRs with passing tests. Elapsed time and the PRs are on screen.
- **Prototype time: ~47 min.** The build session was created at 14:19 UTC, and all four PRs were merged by 15:06 (session metadata + `BUILD_LOG.md`).

**Honest framing:** show any corrections needed in review. That's realistic, and it's the control point.

## Honest evaluation: where Devin is better and where it isn't (3:05–4:00)
Full detail: `docs/EVALUATION.md`.

| Dimension | Power Apps better | Devin-built better |
|---|---|---|
| **Build cost** | Upfront: no platform to build (Build needs ~12.5 eng-weeks + a pen test). Simple forms/CRUD | Each *custom* tool: no connectors or workarounds. Running cost ~$212K vs $421K/yr by Y3; 3-yr $1.04M vs $1.20M (Y1 is +$220K for Build) |
| **Maintenance** | Platform: Microsoft hosts, patches, attests | Apps at 13+: tests, code review, Devin does upgrades across every tool. Still needs a ~0.5 FTE owner |
| **Security** | **Safe by default**: SSO, DLP, column security and audit are configuration | Fits their SDLC and runs in their infrastructure, but **only with discipline**: pen test, branch protection, mandatory rule tests, review of every Devin PR. Devin itself needs a vendor review |
| **Engineering time** | **~0.65 FTE less in Y1, ~0.2 FTE less ongoing.** The strongest argument for Buy | Licence savings (~$200K/yr) roughly fund one engineer; complex Power Apps work consumes engineers anyway |

> **Net:** Build trades ~$200K/yr of licence for ~0.2 FTE of extra engineering and ownership of the security surface. Worth it only if the next tools are mostly custom and the licence really scales with users. Phase 1 exists to measure exactly that.

## What would flip this to Buy (4:00–4:15)
- **The next 10 tools are mostly simple forms/CRUD.** Building blocks are as fast and need no owner.
- Licence under ~$185K, or a flat user count.
- Ops/compliance staff build and edit tools themselves today.
- No team can own the platform, or auditors require Microsoft's attestations.

## Next steps, and where Devin fits (4:15–5:00)
1. **Week 0:** licence audit (users, plan mix, renewal date) and **list the next 10 tools**, classified as simple forms vs. custom logic/integration.
2. **Weeks 1–6 (Devin + 1 owning engineer):**
   - Harden the platform: real SSO, Postgres, deploy, monitoring.
   - Build **the highest-value tool on their list first, on their real systems** (real provider, real data, real edge cases), then one more and the feature-flag migration. The prototype proved the mechanism on mocks; this proves delivery. If Devin handles the hardest tool, the easier ones aren't in question; if it can't, they find out in weeks, not at renewal.
   - **Gate:** eng-weeks per tool, owner hours, incidents.
3. All new tools go on the platform. Refunds next; KYC after a pen test. Drop Power Apps at renewal **only if the gate passes**.
4. **If you choose Buy:** optimise the licence (per-app or pay-as-you-go for light users). Devin still fits for custom connectors, code components and Azure Functions, which is where Power Apps teams hit code anyway.

---

## What to build, ranked by support for the thesis
| Rank | Item | Built by | Supports |
|---|---|---|---|
| 1 | **Platform core:** mock SSO + role switch, `require_role`, audit (same transaction), field masking + audited reveal (rules in one place), version-checked updates, approval/state-machine helpers, integration-adapter pattern, app registry/launcher | Me (Devin), in this session | P1, P3 |
| 2 | **`AGENTS.md`:** the platform rules a new tool must follow, plus a tool template | Me | **P3** |
| 3 | **Refunds** worked example: SoD, dual approval, mock provider with timeout, one-time execution key, reconcile | Me | **P2** |
| 4 | pytest per rule + GitHub Actions CI | Me | P2, P3 |
| 5 | **KYC queue + feature-flag admin**, each built by a **fresh Devin session in parallel** from one paragraph; PRs reviewed and merged | Child Devin sessions | **P3** |
| 6 | Audit log page + shared masking-rule change demo | Me | P1 |

**Time plan (2h cap):** platform + `AGENTS.md` ~50 min → refunds + tests + CI ~30 min → launch 2 child sessions (they run in parallel, ~30 min) → review/merge + README ~10 min.
**Cut line:** if the child sessions overrun, demo whatever state their PRs are in, as an honest data point. Platform + refunds + one factory-built tool is the minimum.
