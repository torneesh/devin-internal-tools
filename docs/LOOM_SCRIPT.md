# Loom script (≤5 min, ~680 spoken words)
Cues in [brackets]. Delivery: conversational, not read. Numbers on screen as you say them.

---

**[0:00 | face cam or title slide]**
You asked whether your team can use Devin to build internal tools instead of paying about $250K a year for Power Apps. My answer: **yes, build, but as a gated migration, not a rip-and-replace.** You're about to build ten-plus tools nobody has fully specified yet. That decision matters far more than the three apps you have today.

**[0:30 | slide: "What Power Apps sells"]**
So what are you actually paying Microsoft for? It isn't drag-and-drop. It's **speed and governance, repeated across many tools.** A small team ships a tool in days, and every tool comes with sign-in, roles, field masking, audit and managed environments that nobody had to build.
The catch is that the building blocks run out. Custom logic, your own APIs, automated testing (Microsoft has deprecated its Test Engine), and scale: their own docs say large queries can silently return incomplete results. Every new bespoke tool makes hitting that ceiling more likely.
So the real question is: **can Devin match that speed and governance for any tool, including the ones that outgrow the building blocks?** Here's what I built in under two hours.

**[1:10 | demo: launcher → switch user]**
First, governance built once. This is one shared platform. When I switch from a support agent to an approver, permissions change. This bank account is masked. To reveal it I have to give a reason, and that reason lands here, in an append-only audit log. Masking rules live in one file, so if I change a rule, every tool picks it up. Tool thirteen is as governed as tool one.

**[1:45 | demo: refunds]**
Second, logic beyond the building blocks. Refunds is the worked example. Alice requests $2,500 and can't approve her own refund. Bob approves, but it's over the threshold, so it needs a second, different approver. Now I execute, and the mock payment provider times out *after* accepting. We don't mark that "failed"; we mark it **unknown**. Reconcile checks with the provider and finds it paid. Retry, and it doesn't pay twice. [cut to test run] Each of those rules is a named test that runs on every PR.

**[2:25 | demo: PRs from child sessions]**
Third, and most important: the tool factory. I gave two brand-new Devin sessions one paragraph each, in business language only: a KYC review queue and a feature-flag admin. I never mentioned audit, masking or roles. They ran in parallel, took [X] and [Y] minutes, and opened these PRs. [show diff] They used the platform's audit, roles and masking because the repo's rules file told them to. [Be honest:] Here's what I had to fix in review: [Z]. That review step is your control point.

**[3:05 | slide: evaluation scorecard]**
So, honestly: where is this better, and where isn't it?
**Build cost:** Power Apps wins upfront. There's no platform to build, and for simple forms it's as fast. Devin wins on each custom tool and on running cost: about $212K a year versus $421K by year three. Over three years, $1.04 million versus $1.2 million, though year one costs more because the licence runs until renewal.
**Maintenance:** Microsoft patches and hosts Power Apps; with Build, that's yours, roughly half an engineer to own it. But across thirteen tools, real code with tests, plus Devin doing upgrades, is easier to maintain than thirteen canvas apps.
**Security:** Power Apps is safer by default. Build can match it and fit your SDLC, but only with discipline: a pen test, mandatory tests, and a human reviewing every Devin PR.
**Engineering time** is the strongest argument for buying: Build costs about two-thirds of an engineer more in year one, and a fifth of one ongoing.
Net: you're trading about $200K a year of licence for a fifth of an engineer and owning the security surface.

**[4:00 | slide: what flips it]**
What would change my mind: if your next ten tools are mostly simple forms, if the licence is really under about $185K, if your ops staff build these tools themselves today, or if nobody can own the platform. Then keep Power Apps.

**[4:15 | slide: next steps]**
Next steps. Week zero: send me your licence breakdown and the list of the next ten tools, and we'll classify each as simple form versus custom logic. Then six weeks with Devin and one owning engineer: harden the platform, build two new tools on it, and migrate the feature-flag admin. Measure engineering weeks per tool and owner hours. If the numbers hold, drop Power Apps at renewal.
And if you decide to keep Power Apps, Devin still fits: custom connectors, code components and Azure Functions are where Power Apps teams end up writing code anyway. Thanks.
