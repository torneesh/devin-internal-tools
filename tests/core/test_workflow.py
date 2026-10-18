import pytest

from core.errors import InvalidTransition, RuleViolation
from core.workflow import ApprovalPolicy, StateMachine


def test_state_machine():
    flow = StateMachine({"OPEN": {"DONE", "CANCELLED"}, "DONE": set()})
    assert flow.can("OPEN", "DONE") and not flow.can("DONE", "OPEN")
    assert flow.states == ["OPEN", "DONE", "CANCELLED"]
    with pytest.raises(InvalidTransition):
        flow.check("DONE", "OPEN")


def test_approval_policy():
    policy = ApprovalPolicy(threshold=100, above_threshold=2)
    assert policy.required(100) == 1 and policy.required(101) == 2
    with pytest.raises(RuleViolation):
        policy.check("ann", "ann")
    with pytest.raises(RuleViolation):
        policy.check("bob", "ann", existing=["bob"])
    assert not policy.satisfied(101, ["bob", "bob"])
    assert policy.satisfied(101, ["bob", "cat"])
