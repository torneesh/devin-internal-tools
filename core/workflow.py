"""State machines and approval rules (separation of duties)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from core.errors import InvalidTransition, RuleViolation


class StateMachine:
    def __init__(self, transitions: Mapping[str, Iterable[str]]):
        self.transitions = {state: frozenset(targets) for state, targets in transitions.items()}

    @property
    def states(self) -> list[str]:
        seen = dict.fromkeys(self.transitions)
        for targets in self.transitions.values():
            seen.update(dict.fromkeys(sorted(targets)))
        return list(seen)

    def allowed(self, current: str) -> frozenset[str]:
        return self.transitions.get(current, frozenset())

    def can(self, current: str, target: str) -> bool:
        return target in self.allowed(current)

    def check(self, current: str, target: str) -> None:
        if not self.can(current, target):
            raise InvalidTransition(f"Can't move from {current} to {target}.")


@dataclass(frozen=True)
class ApprovalPolicy:
    """Approvers must differ from the requester and from each other.

    Values above `threshold` need `above_threshold` distinct approvers; otherwise one.
    """

    threshold: int | None = None
    above_threshold: int = 2

    def required(self, value: int = 0) -> int:
        if self.threshold is not None and value > self.threshold:
            return self.above_threshold
        return 1

    def check(self, approver: str, requester: str, existing: Iterable[str] = ()) -> None:
        if approver == requester:
            raise RuleViolation("You can't approve your own request (separation of duties).")
        if approver in set(existing):
            raise RuleViolation("You've already approved this. A different approver is needed.")

    def satisfied(self, value: int, approvers: Iterable[str]) -> bool:
        return len(set(approvers)) >= self.required(value)
