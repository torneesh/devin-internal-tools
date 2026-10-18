# Evaluation: Devin-built platform vs Power Apps, for this client
Four dimensions from the brief. Each gets a verdict, the evidence behind it, and what would change it.
Numbers come from `analysis/cost_model.py` (base case) and Microsoft/Devin docs (`docs/RESEARCH.md`, `docs/COST_MODEL.md`).

## Scorecard (the pitch slide)
| Dimension | Better | By how much | Holds if… |
|---|---|---|---|
| Upfront build cost | **Power Apps** | Clearly: Build needs ~12.5 eng-weeks of platform + migration, plus a pen test | — |
| Cost per tool: simple forms/CRUD | **Power Apps** | Slightly: building blocks are as fast, and ops staff can do it | — |
| Cost per tool: custom logic / own APIs | **Devin** | Clearly: no custom connectors, no delegation workarounds | Platform + `AGENTS.md` keep tools consistent |
| Running cost (year 2+) | **Devin** | ~$200K/yr ($212K vs $421K in Y3) | Licence really is ~1,000 per-user seats |
| 3-year total | **Devin, narrowly** | $1.04M vs $1.20M; Y1 is +$220K for Build | Licence > ~$185K with growth; build stays on budget |
| Platform maintenance | **Power Apps** | Clearly: Microsoft patches, hosts, attests | — |
| Maintaining 13+ tools | **Devin** | Moderately: tests, code review, Devin does upgrades across all tools | Someone owns the platform |
| Security by default | **Power Apps** | Clearly: SSO, DLP, column security, auditing are configuration | — |
| Security ceiling / fit with their SDLC | **Devin** | Moderately: one review/test/pen-test process, runs in their infrastructure | Discipline: pen test, branch protection, mandatory tests |
| Engineering time (opportunity cost) | **Power Apps** | ~+0.65 FTE in Y1, ~+0.2 FTE ongoing for Build | Devin per-tool speed-up holds |
| Customisation / control | **Devin** | Clearly | — |
| Ops self-service | **Power Apps** | Clearly: a real capability lost | Matters only if ops edit tools today |

**Net:** Power Apps wins on **safety by default, upfront cost, and engineering time**. Devin wins on **running cost, custom tools, testability and control**. Build effectively trades **~$200K/yr of licence for ~0.2 FTE of extra engineering and ownership of the security surface.** That's worth it only if the next tools are mostly custom, and the licence really scales with users.

---

## 1. Build cost
| | Power Apps | Devin-built platform |
|---|---|---|
| One-off | ~$0 (already in place) | Platform hardening ~8 wk + migrating 3 apps ~4.5 wk (≈ $62K) + pen test ~$20K |
| Per new tool | ~2 eng-weeks (assumption). **Faster for simple forms**; slower once it needs custom logic, connectors or workarounds | ~1.25 eng-weeks (assumption). Prototype evidence: platform + refunds built in <2h; factory tools built from one paragraph in [X]/[Y] min, plus review |
| Licence / tooling | ~$250K/yr; unlimited apps per Premium user, so **new tools are ~free and new users aren't** | Devin ~$10–30K/yr (Teams list $40/seat/mo + credits; Enterprise quote-only) + ~$15K hosting |

**Verdict:** Power Apps is cheaper to start; Devin is cheaper per *complex* tool and much cheaper to run.
**Uncertainty:** per-tool weeks are assumptions. The factory demo is n=2, so it shows the mechanism, not a measured rate.

## 2. Maintenance burden
| | Power Apps | Devin-built platform |
|---|---|---|
| Platform | Microsoft hosts and patches; admin/ALM ~0.25 FTE | **Client owns it:** dependency upgrades, hosting, on-call. ~0.5 FTE owner |
| Apps | Power Fx/canvas apps are hard to diff, review and test. **Test Engine is deprecated** (repo removed Nov 2026). Maker leaves → knowledge leaves | Normal code: tests in CI, code review, refactor all tools at once. Devin opens upgrade/fix PRs |
| Vendor change | Microsoft controls the roadmap: deprecations, licence changes | The client controls the roadmap; a platform bug can affect every tool (but one fix fixes them all) |

**Verdict:** Power Apps is lighter on *platform* upkeep. Build is lighter on *app* upkeep as tools multiply. Net, Build carries ~0.25 FTE more ownership, and **Devin reduces the toil but doesn't replace the owner.**

## 3. Security implications
| | Power Apps | Devin-built platform |
|---|---|---|
| Identity & access | Entra SSO, Conditional Access, roles: configuration | Client integrates OIDC with their IdP; RBAC is code (built once in `core/`) |
| Sensitive data | Column security + masking (needs a Managed Environment); DLP on connectors | Central masking policy + audited reveal; data stays in their infrastructure |
| Audit | Dataverse auditing (changes and access) | Append-only audit in the same transaction; client must protect its integrity |
| Compliance evidence | Microsoft attests the platform; **shared responsibility**: the client still owns app logic, access config, data and integrations | All on the client, but through the **same SDLC evidence** they already produce for SOC2 |
| New risks | Misconfigured sharing/DLP, citizen-dev sprawl, code apps served from a public endpoint | Bugs in home-grown auth/masking; **Devin is a new vendor with code access** (needs a vendor security review; Enterprise offers SSO and a dedicated deployment option) |

**Verdict:** Power Apps is **safer by default**. Build can match it and fit their SDLC better, but **only with discipline**: pen test, branch protection, mandatory rule tests, and human review of every Devin PR. That's the biggest risk in the Build option.

## 4. Opportunity cost of engineering time
| Engineering time | Y1 | Y2 | Y3 |
|---|---|---|---|
| Power Apps | 25 wk (0.54 FTE) | 24 wk (0.52 FTE) | 18 wk (0.39 FTE) |
| Devin-built | 56 wk (1.22 FTE) | 32.5 wk (0.71 FTE) | 29.5 wk (0.64 FTE) |

- Build costs **~0.65 FTE more in year 1** and **~0.2–0.25 FTE more ongoing**. That's ~1% of a 60-engineer org, but at a Series C fintech, engineer time is the scarcest resource.
- Devin narrows the gap (1.25 vs 2 wk per tool) but doesn't close it, because the platform needs an owner.
- On the other side: complex tools built in Power Apps still consume engineers, in a separate toolchain (Power Fx, custom connectors, ALM), and the licence money (~$200K/yr from Y2) could fund roughly one engineer.

**Verdict:** Power Apps is cheaper in engineer time. **This is the strongest argument for Buy** and should be said plainly.

## What this means for the recommendation
The evaluation supports **Build, gated**, not Build, unconditionally:
1. **Gate on the two inputs** that flip most rows: the licence breakdown (user count, plan mix) and the mix of the next 10 tools (simple forms vs custom logic).
2. **Phase 1 measures what's assumed here:** actual eng-weeks per tool, owner hours, incidents. That replaces the assumption-driven rows with real numbers before the licence decision at renewal.
3. If phase 1 shows Build costing more engineer time than the licence saves, **stay on Power Apps**, optimise the licence, and use Devin for the code-heavy edges (custom connectors, components, Azure Functions).
