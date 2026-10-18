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
**Evidence (refunds, as a worked example):**
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
- **Total prototype time: under 2 hours** (logged). That includes the platform.

**Honest framing:** show any corrections needed in review. That's realistic, and it's the control point.

## Cost: modest, conditional, scales with users (3:05–3:30)
| 3-year (base case) | Buy | Build |
|---|---|---|
| Total | $1.20M | $1.04M |
| Year 1 | $375K | $595K (licence runs until renewal) |
| Year 3 run-rate | $421K | $212K |

- **Break-even:** licence above ~$185K/yr with user growth, or ~$225K flat.
- Premium covers unlimited apps, so **new tools don't raise the licence; new users do.**
- Hybrid (Power Apps code apps built by Devin) costs the most in every scenario: a transition at best.

## Risks, said out loud (3:30–4:00)
| Risk | Mitigation |
|---|---|
| You own SSO, PII handling and audit integrity | Built once in the platform; external pen test; Devin Enterprise if SSO/data residency is required |
| 13+ tools to maintain | One platform, one owner (~0.5 FTE); Devin does upgrades and fixes as PRs |
| AI-written code touching money/PII | Every change is a reviewed PR; platform rules + mandatory tests; branch protection |
| Ops staff lose self-service edits | Requests go via Slack/Jira → Devin drafts the PR → an engineer approves. Slower than self-serve; trade-off made explicit |
| Year 1 costs more | Migrate before renewal; gate on measured phase-1 numbers |

## What would flip this to Buy (4:00–4:15)
- **The next 10 tools are mostly simple forms/CRUD.** Building blocks are as fast and need no owner.
- Licence under ~$185K, or a flat user count.
- Ops/compliance staff build and edit tools themselves today.
- No team can own the platform, or auditors require Microsoft's attestations.

## Next steps, and where Devin fits (4:15–5:00)
1. **Week 0:** licence audit (users, plan mix, renewal date) and **list the next 10 tools**, classified as simple forms vs. custom logic/integration.
2. **Weeks 1–6 (Devin + 1 owning engineer):**
   - Harden the platform: real SSO, Postgres, deploy, monitoring.
   - Build **2 of the new tools** on it and migrate the feature-flag admin.
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
