# How to show Devin saves engineering capacity: success metrics

## Why owner time is the metric
The base cost model budgets a half-time human platform owner ($115K/yr, the largest ongoing Build cost) for upgrades, pen-test fixes, access reviews, audit evidence and on-call. But Devin can **do** most of that work: dependency upgrades, CVE and pen-test fixes, access-review reports, audit-evidence exports and first-pass incident triage. The human role shrinks to **reviewing and approving**. So the owner's human hours are the number to measure, not a fixed cost.

## What the owner assumption does to the answer (`analysis/cost_model.py`)
| Scenario | Build 3-yr | Build engineers/yr (Y1 / Y2 / Y3) | Buy engineers/yr |
|---|---|---|---|
| Base (0.5 FTE owner) | $1,035K | 1.22 / 0.71 / 0.64 | 0.54 / 0.52 / 0.39 |
| Owner 0.25 FTE | $862K | 0.97 / 0.46 / 0.39 | same |
| Owner 0.15 FTE (~6 h/week reviewing Devin's PRs) | $794K | 0.87 / 0.36 / 0.29 | same |
| Optimistic (0.25 owner, 2 wk platform, 1.5 wk migration, 0.5 wk/tool) | $780K | 0.67 / 0.39 / 0.39 | same |
| Optimistic + 0.15 owner | **$711K** | **0.57 / 0.29 / 0.29** | same |

Buy is **$1,203K** in every row.
**The headline this unlocks:** if the owner load is ~0.15 FTE, Build needs **fewer engineers than Power Apps from year 2** (0.29 vs 0.52), not more, and costs ~40% less.
That's the claim Cognition should make, and the pilot should prove it.

## North-star metric
**Human engineering hours per tool, over its life**, i.e. build + run.
Measure the human hours only, not Devin's time. Compare against a baseline for the same tool in Power Apps (the model assumes 2 eng-weeks ≈ 80 h to build, plus 0.5 eng-weeks a year to maintain).

Everything else supports this one number.

## Supporting metrics

| # | Metric | What it shows | How to measure | Proposed pilot target* |
|---|---|---|---|---|
| 1 | **Human hours per new tool** (writing the prompt, review, user acceptance testing) | Build speed | Engineers log review minutes on each PR (a PR label or one-line comment) | ≤ 16 h (vs ~80 h baseline) |
| 2 | **Lead time:** request to production | Speed to the business | Ticket created → deploy timestamp | ≤ 1 week for a custom tool |
| 3 | **Review rounds per Devin PR** | How good the first attempt is | GitHub API: reviews per PR | ≤ 1.5 average (the factory tools took 1) |
| 4 | **Owner load:** human hours a month on platform ops | The real cost driver | Time log + PR review time on platform PRs | ≤ 25 h/month (~0.15 FTE) |
| 5 | **% of maintenance done by Devin** (upgrades, CVEs, pen-test fixes, evidence reports) | Capacity freed | Share of maintenance PRs written by Devin | ≥ 70% |
| 6 | **Time to patch** a critical CVE or pen-test finding | Security isn't traded away | Finding date → merged fix | ≤ 7 days |
| 7 | **Escaped defects and control failures** | Quality holds | Incidents and audit exceptions per tool | 0 high-severity |
| 8 | **Governance coverage** | Controls are really inherited | CI check: each tool has role, audit, masking and stale-write tests | 100% |
| 9 | **Devin spend per human hour saved** | Return on Devin | Devin usage per tool (billing tags) ÷ (baseline hours − actual hours) | < 25% of the cost of the hours saved |
| 10 | **Engineering capacity freed (FTE)** | The number for the board | Σ (baseline − actual human hours) ÷ 1,840 h | ≥ 0.25 FTE by end of pilot |

*Targets are proposals to agree with the client before the pilot starts, not measured results.

## How to track it cheaply
- **Devin billing tags, one per tool:** Devin's usage for each tool shows up automatically.
- **GitHub:** PR open → merge time, review rounds, PRs written by Devin vs humans, and fix time per finding. All of it comes from the API with no extra work.
- **A one-line time log:** reviewers note minutes spent on each PR. It's the only manual input.
- **A baseline:** for the first 2–3 tools, the client estimates the Power Apps effort *before* Devin builds them, so the comparison is honest.
- **A weekly dashboard during the 6-week pilot**, with these 10 numbers.

## The pilot gate (the pass/fail line for dropping Power Apps)
Build continues if, over the pilot:
1. Human hours per tool are ≤ 20% of the baseline.
2. Owner load is ≤ 0.15–0.25 FTE.
3. There are no high-severity control failures.
4. Devin spend is under 25% of the engineering cost it saved.

If any fails, the numbers show it early and cheaply, and Power Apps stays.
