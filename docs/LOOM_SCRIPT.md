# Loom script (≤5 min, ~740 spoken words; at ~150 wpm that's 5:00, so keep the demos brisk)
Cues in [brackets]. Delivery: conversational, not read. Numbers on screen as you say them.

---

**[0:00 | face cam or title slide]**
You asked whether your team can use Devin to build internal tools instead of paying about $250K a year for Power Apps. My answer: **yes, build, but as a gated migration, not a rip-and-replace.** The real decision is the ten-plus tools you haven't specified yet, not the three you have.

**[0:30 | slide: "What Power Apps sells"]**
So what are you actually paying Microsoft for? It isn't drag-and-drop. It's **speed and governance, repeated across many tools.** A small team ships a tool in days, every tool gets sign-in, roles, field masking and audit for free, ops staff can edit simple apps themselves, and Microsoft runs and certifies the platform.
The catch is that the building blocks run out. Custom logic, your own APIs, automated testing (Microsoft has deprecated its Test Engine), and scale: their own docs say large queries can silently return incomplete results. So: **can Devin match that speed and governance for any tool?** Here's what I built with Devin.

**[1:10 | demo: launcher → switch user]**
First, governance built once. This is one shared platform. When I switch from a support agent to an approver, permissions change. This bank account is masked. To reveal it I have to give a reason, and that reason lands here, in an append-only audit log. Masking rules live in one file, so tool thirteen is as governed as tool one.

**[1:45 | demo: refunds]**
Second, logic beyond the building blocks. I deliberately started with your riskiest workflow, money movement, not a form. Alice requests $2,500 and can't approve her own refund. Bob approves, but over the threshold it needs a second approver. Now I execute, and the provider times out *after* accepting. That's not "failed"; it's **unknown**. Reconcile finds it paid. Retry, and it doesn't pay twice. [cut to test run] Each of those rules is a named test that runs on every PR.

**[2:25 | demo: PRs from child sessions]**
Third, and most important: the tool factory. I gave two brand-new Devin sessions one paragraph each, in business language only: a KYC review queue and a feature-flag admin. No mention of audit, masking or roles. They ran in parallel, and opened these PRs, with tests passing, in 6 and 8 minutes. [show diff] They used the platform's controls because the repo's rules file told them to. [Be honest:] Review found no code bugs, only decisions the paragraph didn't cover, like creating a flag pushing it to production. One review round each; both merged within 40 minutes. That review step is your control point.

**[3:05 | slide: evaluation scorecard]**
So, honestly, where is this better and where isn't it?
**Build cost:** Power Apps wins upfront. No platform to build, and simple forms are as fast. Devin wins on each custom tool and on running cost: about $212K versus $421K a year by year three. Over three years, $1.04 million versus $1.2 million.
**Maintenance:** Microsoft patches and hosts Power Apps; with Build, that's yours, roughly half an engineer to own it. But thirteen tools in tested code, with Devin doing the upgrades, are easier to maintain than thirteen canvas apps.
**Security:** Power Apps is safer by default. Build can match it, but only with discipline: a pen test, mandatory tests, and a human reviewing every Devin PR.
**Engineering time** is the strongest argument for buying: Build costs about two-thirds of an engineer more in year one, and a fifth of one ongoing.
What I can't replicate: ops staff editing tools themselves, Microsoft's hosting and compliance certifications, and mobile. The biggest risk is AI-written code touching money and PII, which is why review and tests are mandatory, not optional.
So my recommendation is build, because the tools you're planning are custom, and you trade about $200K a year of licence for a fifth of an engineer. But gate it on real numbers.

**[4:05 | slide: what flips it]**
What would flip it to buy: if your next ten tools are mostly simple forms, if the licence is really under about $185K, if your ops staff build these tools themselves today, or if nobody can own the platform. Then keep Power Apps.

**[4:20 | slide: next steps]**
Next steps. Week zero: send me your licence breakdown and the list of the next ten tools, and we'll classify each as simple form versus custom logic. Then six weeks with Devin and one owning engineer: harden and pen-test the platform, then build the highest-value tool on your list first, on your real systems. If Devin handles your hardest tool, the easy ones aren't in question. If the numbers hold, drop Power Apps at renewal.
If you keep Power Apps instead, first move light users to per-app or pay-as-you-go licences; if most are light users, that could cut the bill by up to $100K. Devin still fits there too, writing the custom connectors and code components where Power Apps teams end up writing code anyway. Thanks.
