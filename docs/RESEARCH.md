# Power Apps research: what it does, what it costs, where it falls short
Checked against Microsoft docs on 2026-10-17. ✅ = confirmed in docs; ⚠️ = caveat that matters for this client.

## 1. Pricing: what does $250K buy?
- **Power Apps Premium: $20/user/month** (annual). **$12/user/month** with a 2,000-seat minimum. ([pricing](https://www.microsoft.com/en-us/power-platform/products/power-apps/pricing)) ✅
- Each seat includes 250 MB Dataverse DB + 2 GB file entitlement. Extra capacity is sold as add-ons. ✅
- ⚠️ $250K ÷ $240/user/yr ≈ **~1,000 Premium users at list price**. Either the tools serve a large ops, finance and compliance population (which would back up your point about engineers vs. users), or the $250K includes other spend: Power Automate, capacity add-ons, Dynamics or a partner. **This is the first question for the VP.** It decides whether cost scales with ops headcount.

## 2. Security and data protection
- **Entra ID auth, Conditional Access, security roles.** ✅
- **Column-level security + masking rules.** Regex-based masking; authorised users can unmask one record at a time. ⚠️ Masking **requires a Managed Environment**. ([masking](https://learn.microsoft.com/en-us/power-platform/admin/create-manage-masking-rules)) ✅
- **Dataverse auditing.** Record-level and environment-wide audit history. Logs data changes *and* user access. Consumes log storage capacity. ([auditing](https://learn.microsoft.com/en-us/power-platform/admin/manage-dataverse-auditing)) ✅
- **DLP / data policies** restrict which connectors data can flow to, enforced via Managed Environments. ([data policies](https://learn.microsoft.com/en-us/power-platform/admin/managed-environment-data-policies)) ✅
- **Compliance.** Microsoft states it's a **shared responsibility**: Microsoft covers the platform, the customer covers apps, configuration and data. ([compliance](https://learn.microsoft.com/en-us/power-platform/guidance/adoption/compliance)) ✅

## 3. Building and changing apps
- Canvas apps (Power Fx formulas), model-driven apps (on top of Dataverse), Power Pages. ✅
- **Copilot can generate apps from natural language.** ⚠️ Preview, region-dependent. ([Copilot](https://learn.microsoft.com/en-us/power-apps/maker/canvas-apps/ai-conversations-create-app)) ✅
- **Code components (PCF):** custom TypeScript controls packaged into solutions. ✅
- **Code apps (important): Microsoft now lets developers build React/Vue apps in VS Code and host them on Power Platform.** These get Entra auth, 1,500+ connectors callable from JS, DLP and Conditional Access. ([code apps](https://learn.microsoft.com/en-us/power-apps/developer/code-apps/overview)) ✅
  - ⚠️ End users still need a **Premium license** (or pay-as-you-go / App Pass).
  - ⚠️ Code apps **don't support Power Platform Git integration**, and the compiled assets are served from a public endpoint (IP restriction is via Conditional Access only).

## 4. Releases, testing and recovery
- **Git integration is GA** (Apr 2025). It syncs solutions to Git, and Microsoft's reference architecture uses PRs + branch protection + pipelines. ([GA blog](https://www.microsoft.com/en-us/power-platform/blog/power-apps/git-integration-is-generally-available/), [ALM architecture](https://learn.microsoft.com/en-us/power-platform/architecture/reference-architectures/enterprise-power-platform-alm)) ✅
- ⚠️ **Power Apps Test Engine is deprecated.** Its repo is removed **Nov 1, 2026**. Microsoft points to Playwright samples instead. So automated testing of Power Apps business rules is weak and changing right now. ([Test Engine](https://github.com/microsoft/PowerApps-TestEngine)) ✅
- Backup/restore exists for Dataverse environments. It doesn't cover external systems (payment provider, flag service). (Linked earlier in your notes.)

## 5. Scale and integration limits
- ⚠️ **Delegation.** Non-delegable queries only process the first **500 records** (configurable up to 10,000) and **can silently return incorrect results** on larger tables. That's a real risk for a KYC queue or transaction search. ([delegation](https://learn.microsoft.com/en-us/power-apps/maker/canvas-apps/delegation-overview)) ✅
- ⚠️ **Request limits:** 40,000 Power Platform requests per user per 24h (6,000 on per-app / pay-as-you-go). ([limits](https://learn.microsoft.com/en-us/power-platform/admin/api-request-limits-allocations)) ✅
- **Connectors:** 1,000+ prebuilt. Internal APIs need **custom connectors** (a REST wrapper; Entra auth recommended), and private APIs need an on-premises data gateway. ([custom connectors](https://learn.microsoft.com/en-us/connectors/custom-connectors/)) ✅ For a fintech whose systems are its own APIs, the connector count matters less than it sounds.

## 6. Verdict on our two hypothesis lists

| Claimed Devin/build advantage | Holds up? |
|---|---|
| More control over behaviour | ✅ Yes, though narrower than assumed: **code apps** give full UI/logic control inside Power Platform |
| Closer integration with their systems | ✅ Yes. In-house APIs need custom connectors + gateway on Power Platform; built tools call them directly |
| Code under their control | ✅ Mostly. Git integration exists, but **not for code apps**, and canvas apps are Power Fx/YAML, not their stack |
| Reusable foundations | ⚠️ Partly. Power Apps has component libraries, and Dataverse security is reused across apps for free |
| Potential licence savings | ✅ Real **if** cost is per-user (~1,000 users implied). Every code-app user still needs Premium |
| One SDLC/control framework | ✅ Yes. Power Platform ALM is a separate process to staff and evidence |
| Testable business rules | ✅ **Strong.** Test Engine is deprecated; pytest/CI is mature |
| Correctness at scale | ✅ **Strong.** The delegation limits are a real correctness risk for queues/search |
| Maintenance done by Devin | ✅ Applies to built code. Power Fx canvas apps are harder for an agent to work on |

**Where Power Apps clearly wins (confirmed):** column masking, auditing, DLP and Entra are configuration, not code. Hosting and platform attestation are Microsoft's. Copilot/canvas let non-engineers build.

## 7. New option this research surfaces: "Buy the platform, build the apps with Devin"
**Power Apps code apps** let engineers (or Devin) write normal React/TS code while Power Platform supplies Entra auth, connectors, DLP and hosting. That's a credible **middle path**:
- Keep the governance Microsoft already provides.
- Get code-level control and Devin-driven development.

The cost: the licence stays, and code apps have notable limits (no Git integration, public asset endpoint). It belongs in the recommendation as a real alternative, not a footnote.
