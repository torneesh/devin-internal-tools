# Key Decisions: raw material (rewrite in your own words, max 1 page)

## Framing decision
- I treated the question as "can we repeatedly build *unknown future* tools fast with governance built in?", not "can we clone 3 apps". The 10+ planned tools are the purchase decision; the existing 3 are examples.
- Power Apps' value for this client = speed × governance (identity, field protection, audit, approvals, environments) + a managed platform + citizen dev. The drag-and-drop UI isn't the value.
- Research changed the shape of the answer:
  - Premium is $20/user/mo with unlimited apps → $250K ≈ 1,000 users. New tools don't raise the licence; users do.
  - Power Apps **code apps** made "hybrid" a real option. The cost model then showed it's the most expensive in every scenario, so it collapsed back to two choices.

## Scope decisions (what I built and why)
- **A shared platform, not three apps.** Governance is built once and inherited, which is the only way 13+ tools stay governed and maintainable.
- **Refunds as the single hand-built worked example:** money movement plus failure handling (timeout → UNKNOWN → reconcile, idempotent retry) shows "beyond the building blocks" better than any CRUD screen.
- **The tool factory as the centrepiece:** two fresh Devin sessions in parallel, given business-language prompts with **no mention of controls**, to test whether `AGENTS.md` makes controls inherited by default. Results are reported as-is, including fixes needed.
- **Deliberately not built:** real SSO, Postgres, deployment, monitoring, a drag-and-drop builder. They're well-understood or irrelevant to the decision, and building them would make a 2-hour proof of concept less plausible.

## Architecture decisions and trade-offs
| Decision | Why | Trade-off accepted |
|---|---|---|
| Python/FastAPI + server-rendered Jinja/HTMX | One language, easy to debug, no frontend build; enough for internal tools | Less rich UI than React/canvas |
| Platform as an importable `core/` package + `AGENTS.md` + a tool template | Encodes the rules for both humans and Devin; one fix applies everywhere | Platform becomes critical shared code that needs an owner |
| Rules in a service layer, audit in the same DB transaction | Can't have a change without its audit record | More boilerplate per tool (mitigated by the template) |
| Optimistic concurrency (version column) | Detects stale writes without locks | Users sometimes have to reload and redo |
| Idempotency key persisted *before* calling the provider | The only way to make retries safe across a timeout | Needs a reconcile path and an UNKNOWN state |
| Central masking policy rendered via one macro | One-line change propagates to every tool | Masking at render, not at query; production should mask in the API layer too |
| SQLite locally | Zero setup for reviewers | Postgres needed for prod (SQL kept portable) |

## Biggest uncertainties
- Licence breakdown and the mix of the next 10 tools (simple forms vs custom logic) decide the answer.
- Whether 0.5 FTE is enough to own the platform; whether ops staff edit apps today.
- The factory demo is n=2, which shows the mechanism, not a rate.
