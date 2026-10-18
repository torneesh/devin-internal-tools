"""Mock flag service (e.g. LaunchDarkly / Unleash / an in-house config service).

Pushes carry the full desired state plus a revision, so a retry is always safe and a push that
arrives after a newer one is ignored. `available = False` simulates an outage (demo + tests).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core import integrations


class FlagServiceUnavailable(Exception):
    pass


@dataclass(frozen=True)
class LiveFlag:
    enabled: bool
    rollout_pct: int
    revision: int


@dataclass
class MockFlagService:
    name: str = "flag_service"
    available: bool = True
    live: dict[tuple[str, str], LiveFlag] = field(default_factory=dict)
    received: list[tuple[str, str, LiveFlag]] = field(default_factory=list)  # every accepted push

    def push(
        self, environment: str, key: str, *, enabled: bool, rollout_pct: int, revision: int
    ) -> LiveFlag:
        if not self.available:
            raise FlagServiceUnavailable("Flag service unavailable (simulated outage)")
        current = self.live.get((environment, key))
        if current and current.revision > revision:
            return current  # a newer change already landed
        pushed = LiveFlag(enabled, rollout_pct, revision)
        self.live[(environment, key)] = pushed
        self.received.append((environment, key, pushed))
        return pushed

    def get(self, environment: str, key: str) -> LiveFlag | None:
        return self.live.get((environment, key))


integrations.register(MockFlagService())
