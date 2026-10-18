# Build log

No hard cap for this run (the user confirmed at kickoff). Timestamps are still logged for each block in `docs/BUILD_SPEC.md` §6. All times are UTC.

| Time (UTC) | Block | Note |
|---|---|---|
| 2026-10-18 14:21 | **Start** | Clock started. Branch `devin/1792333264-platform-refunds` |
| 2026-10-18 14:21 | Platform core + templates + seed + core tests | started |
| 2026-10-18 14:25 | Platform core + templates + seed + core tests | done. Login switch, append-only audit (DB triggers), masking + audited reveal, 409 on stale write (ORM version guard). |
| 2026-10-18 14:25 | `AGENTS.md` + `_template` | started (the template tool was written with the core and has passing tests) |
| 2026-10-18 14:25 | `AGENTS.md` + `_template` | done. Template tool passes lint and tests. |
| 2026-10-18 14:25 | Refunds + tests + CI | the refunds tool and all 10 section-3 tests pass locally. Opening the PR for CI. |
| 2026-10-18 14:26 | Refunds + tests + CI | done. [PR #1](https://github.com/torneesh/devin-internal-tools/pull/1): `lint-and-test` passed in GitHub Actions and the PR was merged to `main` at 14:26:29. |
| 2026-10-18 14:26 | Launch A + B in parallel | done. Both child sessions were created at 14:26:35 from the exact §5 prompts: [KYC](https://app.devin.ai/sessions/339f1fd6fc604a74b30433597b06c457), [flags](https://app.devin.ai/sessions/db1aceb4645f4792b468d8be024b9821). |
| 2026-10-18 14:27 | README + audit page + masking-policy demo | started. The audit page and masking policies shipped in PR #1; this block covers the README and the demo script. |
| 2026-10-18 14:32 | Review/merge A + B | KYC [PR #2](https://github.com/torneesh/devin-internal-tools/pull/2) opened, CI green (14:32:40, 6 min after launch). |
| 2026-10-18 14:34 | Review/merge A + B | Flags [PR #3](https://github.com/torneesh/devin-internal-tools/pull/3) opened, CI green (14:34:35, 8 min after launch). README committed on `devin/1792333600-docs-factory` meanwhile. |
| 2026-10-18 14:40 | Review/merge A + B | Round 1 review done on both PRs. No code defects. Three product decisions taken by the owner and sent back to the sessions (see `docs/FACTORY_RESULTS.md`). |
| 2026-10-18 14:56 | Review/merge A + B | Flags round-2 fix verified (CI green, 60 tests) and [PR #3](https://github.com/torneesh/devin-internal-tools/pull/3) merged at 14:56:42. KYC still working on the claimant-only reveal (needs a `core/masking` hook). |
| 2026-10-18 15:04 | Review/merge A + B | KYC round-2 fix verified locally (90 tests, lint clean) and [PR #2](https://github.com/torneesh/devin-internal-tools/pull/2) merged at 15:04:07. Both factory tools are on `main`. |
| 2026-10-18 15:06 | Docs | `docs/FACTORY_RESULTS.md` finished, README updated for the merged tools, docs branch merged with `main` and opened as a PR. |

## Pass 2: real SSO, fake data, Power Apps-style shell
Separate from the timed build above. Branch `devin/1792343517-sso-fake-data-ui`.

| Time (UTC) | Block | Notes |
|---|---|---|
| 2026-10-18 17:11 | **Start** | Keycloak 26 in Docker Compose, realm generated from `seed.py` users, groups = roles. |
| 2026-10-18 17:15 | SSO + fake data | OIDC sign-in end to end through Keycloak (bob, alice), group roles synced and audited. Faker seed: 48 refunds, 40 KYC cases, 13 flags across every status, created through the services so rules and audit apply. |
| 2026-10-18 17:16 | Light restyle | Fluent-style header, role-filtered left menu and business-process stage bar on refund and KYC records, all in the shared templates. 94 tests, lint clean. |

