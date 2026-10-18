# PII compliance for a fintech: what's required, and does Power Apps cover it?
Researched 2026-10-18 against Microsoft Learn, EUR-Lex and PCI DSS v4.0.1 material. Not legal advice.

**Short answer:** no platform "satisfies" a regulation for you. The regulated company is always responsible, and Microsoft says so itself: compliance is "a shared responsibility of cloud service providers and their customers". What Power Apps gives you is two things:
- **Certified infrastructure.** Microsoft's audits cover the platform.
- **Built-in controls you still have to configure**: column security, masking, auditing, data region and customer-managed keys. Several of these need **Managed Environments**.

The parts regulators actually examine are the client's job on *either* option:
- the access rules,
- the retention and deletion schedule,
- separation of duties,
- the evidence that controls ran.

So compliance doesn't make Power Apps win automatically. It makes Power Apps **cheaper to get to compliant** for simple apps, and it makes Build **more work to evidence**.

> Not legal advice. We don't yet know where the client is licensed or whether it touches card numbers. That changes which regimes below apply. Sources are linked; items marked *(general knowledge)* weren't re-checked against primary sources this session.

---

## 1. Which rules apply to a Series C fintech

| Regime | Applies if… | What it requires for internal tools handling PII |
|---|---|---|
| **GDPR / UK GDPR** | They have EU or UK customers (our demo data is EU) | Security proportionate to risk (Art. 32: access control, encryption, pseudonymisation); a record of what's processed and why (Art. 30); data subject rights such as access and erasure (Arts. 15–17); breach notice within 72 h (Art. 33); impact assessment for high-risk processing (Art. 35); contracts with processors (Art. 28); limits on transfers outside the EU *(article numbers: general knowledge)* |
| **AML / KYC record-keeping** (EU AMLD Art. 40; UK MLR 2017) | They onboard customers (KYC) | Keep identity documents and transaction records **5 years after the relationship ends**, then **delete** (extendable by up to 5 more years) ([EUR-Lex 2015/849](https://eur-lex.europa.eu/eli/dir/2015/849/oj/eng)). This conflicts with GDPR erasure requests, so the tool needs a retention rule per record |
| **PCI DSS v4.0.1** | They store, process or transmit card numbers (PAN) | Show at most the first 6 and last 4 digits, and full PAN only to roles with a documented need (3.4.1); need-to-know access (Req. 7); unique IDs and MFA (Req. 8); audit logs **kept 12 months, last 3 months immediately available** (10.5.1); regular penetration tests (Req. 11) ([PCI DSS 10.5.1](https://www.pcicompliancehub.com/docs/pci-dss/requirements/10-logging/10-5-1), [SAQ text](https://treasurer.nebraska.gov/tm/pci-dss/documents/PCI_DSS_v4_0_1_SAQ_B_IP.pdf)) |
| **SOC 2 Type 2 / ISO 27001** | Not law, but bank partners and B2B customers usually demand it | Evidence over time of: access reviews, change management (who approved each change), logging and monitoring, vendor management, incident response. **Internal tools that touch customer data are in scope** |
| **DORA** (EU regulation, in force since 17 Jan 2025) | They're an EU-regulated financial entity (e-money, payments, credit) | ICT risk management, incident reporting, resilience testing, and **third-party ICT risk**: a register of ICT providers, contract clauses and exit plans. Power Apps *and* Devin would both be ICT third parties ([MS DORA](https://learn.microsoft.com/en-us/compliance/regulatory/offering-home)) |
| **US: GLBA Safeguards Rule** (+ NYDFS Part 500 if NY-licensed, CCPA/CPRA) | US customers *(general knowledge)* | A written security programme, access controls, encryption, MFA, activity logging, vendor oversight, and breach notice to the FTC |

**The recurring requirements, boiled down:**
1. Only the right people see PII (roles plus need-to-know).
2. Show PII masked by default, and log every full view.
3. A tamper-proof audit trail, kept long enough: 12 months for PCI, 5 years of records for AML.
4. Strong identity: SSO, MFA, removing leavers promptly, periodic access reviews.
5. Encryption in transit and at rest, and control over where data lives (residency).
6. Retention *and* deletion on a schedule, plus handling data-subject requests.
7. Change control: every change reviewed, approved and traceable.
8. Third-party management: contracts, risk assessment, exit plans for each vendor.
9. Testing and incident response: pen tests, breach notification.

---

## 2. What Power Apps provides (from Microsoft's docs)

| Need | Power Apps / Power Platform | Catch |
|---|---|---|
| Certified platform | **Power Apps is in scope** of Microsoft's PCI DSS v4.0.1 assessment ([MS PCI](https://learn.microsoft.com/en-us/compliance/regulatory/offering-pci-dss)) and its SOC 2 Type 2 report ([MS SOC 2](https://learn.microsoft.com/en-us/compliance/regulatory/offering-soc-2)) | Microsoft: its certification "doesn't automatically translate to PCI DSS certification for the services that customers build". The app is still the client's |
| Data residency | Environments are pinned to a region; Power Platform is covered by the **EU Data Boundary** ([EUDB](https://learn.microsoft.com/en-us/privacy/eudb/eu-data-boundary-learn), [regions](https://learn.microsoft.com/en-us/power-platform/admin/regions-overview)) | Microsoft notes that users or connectors can move data out of the region |
| Encryption | TLS 1.2+ in transit; Dataverse encrypted at rest (TDE) by default ([MS](https://learn.microsoft.com/en-us/power-platform/admin/wp-compliance-data-privacy)) | **Customer-managed keys** work only on **Managed Environments**, and users need **E5-class** licences ([CMK](https://learn.microsoft.com/en-us/power-platform/admin/customer-managed-key)) |
| Masking and need-to-know | Column-level security plus masking rules; "read unmasked" can be limited to one record at a time ([column security](https://learn.microsoft.com/en-us/power-platform/admin/field-level-security), [masking](https://learn.microsoft.com/en-us/power-platform/admin/create-manage-masking-rules)) | Masking needs a **Managed Environment**. **System administrators always see unmasked data.** The docs we read don't describe asking for a *reason* before revealing |
| Audit trail | Dataverse auditing, retention configurable up to "Forever" ([auditing](https://learn.microsoft.com/en-us/power-platform/admin/manage-dataverse-auditing)) | You have to switch it on per table. It covers Dataverse data; apps on SharePoint or SQL connectors don't get it *(inference)*. Power Automate events in Purview are kept 90 days |
| Identity | Entra ID SSO, MFA, Conditional Access, security roles | Configuration is the client's: roles, access reviews, removing leavers |
| Data-subject requests | Microsoft documents DSR export for Power Apps data ([MS](https://learn.microsoft.com/en-us/power-platform/admin/wp-compliance-data-privacy)) | The AML-vs-erasure retention rules are the client's logic |
| DORA | Microsoft publishes DORA material and readiness resources ([MS](https://learn.microsoft.com/en-us/compliance/regulatory/offering-home)) | The client still keeps Microsoft in its ICT register, with an exit plan |
| Separation of duties, retention schedules, "never pay twice" | **Not provided** | App logic the client builds, on either option |

**Verdict:** Power Apps clears the **infrastructure** boxes and makes the **standard controls** (masking, audit, MFA, residency) a configuration task, as long as they run Managed Environments. It doesn't clear the **business** boxes: who may see what and why, retention versus erasure, separation of duties, access reviews. Those still need design and evidence.

---

## 3. Where our prototype stands on the same list

| Need | Prototype today | For production (Build) |
|---|---|---|
| Certified platform | None of its own | Host on their existing cloud, which is likely already PCI/SOC 2-certified *(general knowledge)*, and bring the platform into their own SOC 2 scope |
| Masking and need-to-know | ✅ Central masking policy, reveal **requires a reason** and is audited, the audit stores masked values, KYC reveal limited to the claimant or a supervisor | Rate-limit reveals; optional approval step; mask in the API layer too |
| Audit trail | ✅ Append-only (database triggers), written in the same transaction as the change, before → after | Postgres plus a write-once log store; 12-month / 5-year retention policy; feed into their monitoring system (SIEM) |
| Identity | ✅ OIDC SSO, groups → roles, role changes audited | Point it at Entra; enforce MFA there; SCIM to remove leavers; quarterly access-review report |
| Separation of duties | ✅ No self-approval; two different approvers over $1K; staging ≠ production | Already better than Power Apps here: tested in code |
| Change control | ✅ Every change is a reviewed PR, with CI tests per rule | Branch protection plus required reviewers (not yet set), which is strong SOC 2 change-management evidence |
| Encryption and residency | ❌ SQLite file, unencrypted | Managed Postgres with encryption at rest and their own keys, in their chosen region |
| Retention, deletion, DSR | ❌ | A retention job per record type (AML 5 years versus GDPR erasure), plus a DSR export |
| Pen test, incident response | ❌ | Pen test before go-live (in the cost model, ~$20K) |
| Third parties | Devin is a new ICT vendor with **code** access | Vendor review; add to the DORA register if they're EU-regulated; **keep production PII out of Devin sessions** (synthetic data only, as in the prototype) |

---

## 4. What this means for the pitch
1. **Be honest on camera:** Power Apps arrives with Microsoft's PCI and SOC 2 coverage, and its masking, audit and MFA are configuration. Build has to *earn* each of those with code, hosting and a pen test. This matches our "security by default → Power Apps" scorecard line.
2. **Where Build is genuinely stronger for regulators:**
   - Business-rule controls (separation of duties, reveal-with-reason, claimant-only access) are **tested code**, with PR history as change evidence.
   - Power Apps' admins see everything unmasked.
3. **New gating questions for week 0:**
   - Do any tools touch card numbers (PCI scope)?
   - Are they EU-regulated (DORA)?
   - Are they already on Managed Environments? (Power Apps' masking and customer-managed keys depend on it.)
   - Who signs off security for their SOC 2 scope?
4. **Production gap list** (also in the README's Known gaps): encryption at rest, a retention/deletion job, DSR export, 12-month log retention and SIEM, branch protection, pen test, Devin vendor review.
