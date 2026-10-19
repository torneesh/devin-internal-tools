# Evaluation: Devin-built platform vs Power Apps, for this client
Four dimensions from the brief. Each gets a verdict, the evidence behind it, and what would change it.
Numbers come from `cost_model.py` (base case) and Microsoft/Devin docs (`RESEARCH.md`, `COST_MODEL.md`).

**Read the cost rows as assumptions.** Most inputs (licence growth, owner time, weeks per tool) are estimates, not measurements. The defensible version is a break-even: the ~$250K/yr licence minus ~$65K/yr of Build running costs (Devin, hosting, pen test) leaves ~$185K/yr, so Build saves money as long as owning the platform takes **less than ~0.8 of an engineer**. A 6-week pilot measures the real figure in human engineering hours per tool and owner hours per week (`SUCCESS_METRICS.md`).

## Scorecard
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
| Engineering time (opportunity cost) | **Power Apps** in the base case | ~+0.65 FTE in Y1, ~+0.2 FTE ongoing for Build | The owner needs ~0.5 FTE. If Devin does the upkeep and the owner only reviews (~0.15 FTE), **Devin** wins from Y2: 0.36 vs 0.52 FTE |
| Customisation / control | **Devin** | Clearly | — |
| Ops self-service | **Power Apps** | Clearly: a real capability lost | Matters only if ops edit tools today |
| Microsoft 365 integration, ready-made connectors | **Power Apps** | Moderately: Teams/Outlook/Excel and hundreds of connectors out of the box; with Build each is integration code to write and maintain | Matters if the next tools lean on Microsoft 365 or SaaS connectors |
| Mobile / offline | **Power Apps** | Out of the box (Power Apps mobile app, offline option). Buildable with Devin, but extra work to build and maintain | Matters only for field staff; these are desk-based tools |

**Net:** Power Apps wins on **safety by default, upfront cost, and engineering time**. Devin wins on **running cost, custom tools, testability and control**. Build effectively trades **~$200K/yr of licence for ~0.2 FTE of extra engineering and ownership of the security surface.** That's worth it only if the next tools are mostly custom, and the licence really scales with users. The swing factor is owner time: if Devin carries the upkeep (~0.15 FTE of human review), Build costs $794K over 3 years and needs fewer engineers than Buy from Y2.

---

## 1. Build cost
| | Power Apps | Devin-built platform |
|---|---|---|
| One-off | ~$0 (already in place) | Platform hardening ~8 wk + migrating 3 apps ~4.5 wk (≈ $62K) + pen test ~$20K |
| Per new tool | ~2 eng-weeks (assumption). **Faster for simple forms**; slower once it needs custom logic, connectors or workarounds | ~1.25 eng-weeks (assumption). Prototype evidence: factory tools went from one paragraph to a green-CI PR in 6 and 8 min, and were merged after one review round at 30 and 38 min (`../FACTORY_RESULTS.md`) |
| Licence / tooling | ~$250K/yr; unlimited apps per Premium user, so **new tools are ~free and new users aren't** | Devin ~$10–30K/yr (Teams list $40/seat/mo + credits; Enterprise quote-only) + ~$15K hosting |

**Verdict:** Power Apps is cheaper to start; Devin is cheaper per *complex* tool and much cheaper to run.
**Uncertainty:** per-tool weeks are assumptions. The factory demo is n=2, so it shows the mechanism, not a measured rate.

## 2. Maintenance burden
| | Power Apps | Devin-built platform |
|---|---|---|
| Platform | Microsoft hosts and patches; admin/ALM ~0.25 FTE | **Client owns it:** dependency upgrades, hosting, on-call. ~0.5 FTE owner in the base case; Devin can write most of the upkeep PRs, leaving the owner to review (0.15–0.25 FTE in the scenarios) |
| Apps | Power Fx/canvas apps are hard to diff, review and test. **Test Engine is deprecated** (repo removed Nov 2026). Maker leaves → knowledge leaves | Normal code: tests in CI, code review, refactor all tools at once. Devin opens upgrade/fix PRs |
| Vendor change | Microsoft controls the roadmap: deprecations, licence changes | The client controls the roadmap; a platform bug can affect every tool (but one fix fixes them all) |

**Verdict:** Power Apps is lighter on *platform* upkeep. Build is lighter on *app* upkeep as tools multiply. Net, Build carries ~0.25 FTE more ownership, in the base case. Devin can do most of the owner's work itself (upgrades, CVE and pen-test fixes, access-review and audit-evidence reports), so **the owner's human hours are the number to measure** in the pilot (`SUCCESS_METRICS.md`).

## 3. Security implications
| | Power Apps | Devin-built platform |
|---|---|---|
| Identity & access | Entra SSO, Conditional Access, roles: configuration | Client integrates OIDC with their IdP (prototype: working OIDC against a local Keycloak, groups → roles); RBAC is code (built once in `core/`) |
| Sensitive data | Column security + masking (needs a Managed Environment); DLP on connectors | Central masking policy + audited reveal; data stays in their infrastructure |
| Audit | Dataverse auditing (changes and access) | Append-only audit in the same transaction; client must protect its integrity |
| Compliance evidence | Microsoft attests the platform; **shared responsibility**: the client still owns app logic, access config, data and integrations | All on the client, but through the **same SDLC evidence** they already produce for SOC2. Requirement-by-requirement detail: `COMPLIANCE.md` |
| New risks | Misconfigured sharing/DLP, citizen-dev sprawl, code apps served from a public endpoint | Bugs in home-grown auth/masking; **Devin is a new vendor with code access** (needs a vendor security review; Enterprise offers SSO and a dedicated deployment option) |

**Pen testing applies to both options.** Microsoft tests its platform, but the client's app configuration (sharing, table permissions, connectors) is theirs to test on Power Apps too. Build's test covers more, because it includes the code. The cost model puts the pen test on Build only, which favours Buy.

**Verdict:** Power Apps is **safer by default**. Build can match it and fit their SDLC better, but **only with discipline**: pen test, branch protection, mandatory rule tests, and human review of every Devin PR. That's the biggest risk in the Build option.

## 4. Opportunity cost of engineering time
| Engineering time | Y1 | Y2 | Y3 |
|---|---|---|---|
| Power Apps | 25 wk (0.54 FTE) | 24 wk (0.52 FTE) | 18 wk (0.39 FTE) |
| Devin-built (base, owner 0.5 FTE) | 56 wk (1.22 FTE) | 32.5 wk (0.71 FTE) | 29.5 wk (0.64 FTE) |
| Devin-built, owner 0.15 FTE | 39.9 wk (0.87 FTE) | 16.4 wk (0.36 FTE) | 13.4 wk (0.29 FTE) |
| Devin-built, optimistic | 26.4 wk (0.57 FTE) | 13.4 wk (0.29 FTE) | 13.4 wk (0.29 FTE) |

- Build costs **~0.65 FTE more in year 1** and **~0.2–0.25 FTE more ongoing**. That's ~1% of a 60-engineer org, but at a Series C fintech, engineer time is the scarcest resource.
- In the base case Devin narrows the gap (1.25 vs 2 wk per tool) but doesn't close it, because the platform needs a half-time owner. If Devin writes the upkeep PRs and the owner only reviews them (~0.15 FTE), Build uses **fewer** engineers than Buy from Y2 (0.36 vs 0.52 FTE). That assumption is what the pilot has to prove.
- On the other side: complex tools built in Power Apps still consume engineers, in a separate toolchain (Power Fx, custom connectors, ALM), and the licence money (~$200K/yr from Y2) could fund roughly one engineer.

**Verdict:** in the base case Power Apps is cheaper in engineer time. **This is the strongest argument for Buy** and should be said plainly, together with the condition that reverses it: owner time.

## What this means for the recommendation
The evaluation supports **Build, gated**, not Build, unconditionally:
1. **Gate on the two inputs** that flip most rows: the licence breakdown (user count, plan mix) and the mix of the next 10 tools (simple forms vs custom logic).
2. **Phase 1 measures what's assumed here:** actual eng-weeks per tool, owner hours, incidents (metrics and pass/fail gate: `SUCCESS_METRICS.md`). That replaces the assumption-driven rows with real numbers before the licence decision at renewal.
3. If phase 1 shows Build costing more engineer time than the licence saves, **stay on Power Apps**, optimise the licence, and use Devin for the code-heavy edges (custom connectors, components, Azure Functions).
