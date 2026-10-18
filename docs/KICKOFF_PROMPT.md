# Kickoff prompt for the build session (paste into a new Devin session)

Repo: https://github.com/torneesh/devin-internal-tools

Build the prototype described in `docs/BUILD_SPEC.md`. Read `docs/PITCH.md` first: the build exists only to support that argument.

- **Hard cap: 2 hours** from when you start. Create `BUILD_LOG.md` with the start time and a timestamp at each block in the spec's time plan.
- Python, following the spec's stack and structure exactly. Don't add scope.
- Work on a branch and open PRs to `main`. CI (ruff + pytest) must be green before merging. Merge your own platform/refunds PR once green, because the child sessions need it on `main`.
- Write `AGENTS.md` before launching the two child sessions. Launch them **in parallel** with the exact prompts in section 5, word for word: don't add hints about the platform.
- Review their PRs as a human reviewer would. Record the results table from section 5 in `docs/FACTORY_RESULTS.md`, including what had to be fixed. Don't quietly fix their work to make it look better.
- Finish with a README: what it is, how to run it, a 2-minute demo script matching the pitch's demo moments, the architecture, and known gaps.
