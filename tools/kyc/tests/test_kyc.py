"""KYC review queue: permissions, one test per rule, stale writes, audit and masking."""

import pytest

from core import audit
from core.errors import (
    InvalidTransition,
    PermissionDenied,
    RuleViolation,
    StaleWrite,
    ValidationError,
)
from tools.kyc import service

GOV_ID = "XK99887766"
DOB = "1990-04-21"


def new_case(db, user, document_status="UPLOADED"):
    return service.create_case(
        db,
        user("erin"),
        customer_name="Test Customer",
        date_of_birth=DOB,
        government_id=GOV_ID,
        country="gb",
        document_status=document_status,
    )


def claimed_case(db, user, analyst="dave", **kwargs):
    case = new_case(db, user, **kwargs)
    return service.claim(db, user(analyst), case.id, case.version)


def escalated_case(db, user, analyst="dave", **kwargs):
    case = claimed_case(db, user, analyst, **kwargs)
    return service.escalate(db, user(analyst), case.id, case.version, "Needs a second look")


# --- permissions: one per action -------------------------------------------------------------


def test_view_requires_kyc_or_auditor_role(db, user, login):
    case = new_case(db, user)
    assert login("frank").get("/kyc").status_code == 403
    assert login("alice").get(f"/kyc/{case.id}").status_code == 403
    for name in ("dave", "erin", "ivan"):
        assert login(name).get(f"/kyc/{case.id}").status_code == 200


def test_create_requires_supervisor(login):
    form = {
        "customer_name": "C",
        "date_of_birth": DOB,
        "government_id": GOV_ID,
        "country": "GB",
        "document_status": "UPLOADED",
    }
    assert login("dave").post("/kyc", data=form).status_code == 403
    assert login("erin").post("/kyc", data=form).status_code == 200


def test_claim_requires_analyst(db, user, login):
    case = new_case(db, user)
    for name in ("erin", "ivan"):
        response = login(name).post(f"/kyc/{case.id}/claim", data={"version": case.version})
        assert response.status_code == 403
    assert db.get(type(case), case.id).status == service.OPEN


@pytest.mark.parametrize("action", ["approve", "reject", "escalate", "release"])
def test_decisions_require_analyst(db, user, login, action):
    case = claimed_case(db, user)
    data = {"version": case.version, "reason": "Looks fine to me"}
    for name in ("erin", "ivan"):
        assert login(name).post(f"/kyc/{case.id}/{action}", data=data).status_code == 403
    args = (db, user("erin"), case.id, case.version)
    with pytest.raises(PermissionDenied):
        if action == "release":
            service.release(*args)
        else:
            getattr(service, action)(*args, "Looks fine to me")


def test_resolve_requires_supervisor(db, user, login):
    case = escalated_case(db, user)
    data = {"version": case.version, "outcome": "APPROVED", "reason": "Verified by phone"}
    for name in ("dave", "heidi", "ivan"):
        assert login(name).post(f"/kyc/{case.id}/resolve", data=data).status_code == 403
    assert db.get(type(case), case.id).status == service.ESCALATED


# --- business rules --------------------------------------------------------------------------


def test_case_must_be_claimed_before_decision(db, user):
    case = new_case(db, user)
    with pytest.raises(InvalidTransition):
        service.approve(db, user("dave"), case.id, case.version, "ok")
    with pytest.raises(InvalidTransition):
        service.escalate(db, user("dave"), case.id, case.version, "unsure")


def test_cannot_claim_a_case_someone_else_claimed(db, user):
    case = claimed_case(db, user, "dave")
    with pytest.raises(InvalidTransition, match="Already claimed by dave"):
        service.claim(db, user("heidi"), case.id, case.version)
    assert case.assigned_to == "dave"


def test_only_claimant_can_approve_reject_escalate_or_release(db, user):
    case = claimed_case(db, user, "dave")
    heidi = user("heidi")
    with pytest.raises(RuleViolation, match="claimed this case"):
        service.approve(db, heidi, case.id, case.version, "Looks fine")
    with pytest.raises(RuleViolation):
        service.reject(db, heidi, case.id, case.version, "Mismatch")
    with pytest.raises(RuleViolation):
        service.escalate(db, heidi, case.id, case.version, "Unsure")
    with pytest.raises(RuleViolation):
        service.release(db, heidi, case.id, case.version)
    assert case.status == service.IN_REVIEW


def test_decisions_require_a_reason(db, user):
    case = claimed_case(db, user)
    for action in (service.approve, service.reject, service.escalate):
        with pytest.raises(ValidationError, match="reason is required"):
            action(db, user("dave"), case.id, case.version, "   ")
    case = service.escalate(db, user("dave"), case.id, case.version, "Unsure")
    with pytest.raises(ValidationError, match="reason is required"):
        service.resolve(db, user("erin"), case.id, case.version, service.APPROVED, "")
    assert case.status == service.ESCALATED


def test_approve_and_reject_store_reason_and_decider(db, user):
    case = claimed_case(db, user)
    case = service.approve(db, user("dave"), case.id, case.version, "ID matches selfie")
    assert (case.status, case.decided_by, case.decision_reason) == (
        service.APPROVED,
        "dave",
        "ID matches selfie",
    )
    other = claimed_case(db, user, "heidi")
    other = service.reject(db, user("heidi"), other.id, other.version, "Name mismatch")
    assert (other.status, other.decision_reason) == (service.REJECTED, "Name mismatch")


def test_cannot_approve_without_uploaded_documents(db, user):
    for docs in ("MISSING", "UNREADABLE"):
        case = claimed_case(db, user, document_status=docs)
        with pytest.raises(RuleViolation, match="documents are uploaded"):
            service.approve(db, user("dave"), case.id, case.version, "Looks fine")
        case = service.reject(db, user("dave"), case.id, case.version, "No usable documents")
        assert case.status == service.REJECTED
    case = escalated_case(db, user, document_status="MISSING")
    with pytest.raises(RuleViolation):
        service.resolve(db, user("erin"), case.id, case.version, service.APPROVED, "ok")


def test_escalated_case_cannot_be_decided_by_analyst(db, user):
    case = escalated_case(db, user)
    with pytest.raises(InvalidTransition):
        service.approve(db, user("dave"), case.id, case.version, "Changed my mind")
    assert (case.escalated_by, case.escalation_reason) == ("dave", "Needs a second look")


def test_only_supervisor_resolves_escalated_cases(db, user):
    case = escalated_case(db, user)
    with pytest.raises(PermissionDenied):
        service.resolve(db, user("dave"), case.id, case.version, service.APPROVED, "ok")
    case = service.resolve(db, user("erin"), case.id, case.version, service.REJECTED, "Forged")
    assert (case.status, case.decided_by, case.decision_reason) == (
        service.REJECTED,
        "erin",
        "Forged",
    )


def test_resolve_only_applies_to_escalated_cases(db, user):
    case = claimed_case(db, user)
    with pytest.raises(InvalidTransition):
        service.resolve(db, user("erin"), case.id, case.version, service.APPROVED, "ok")
    case = escalated_case(db, user)
    with pytest.raises(ValidationError):
        service.resolve(db, user("erin"), case.id, case.version, "MAYBE", "ok")


def test_supervisor_cannot_resolve_own_escalation(db, user):
    admin = user("admin")  # holds both kyc_analyst and kyc_supervisor
    case = escalated_case(db, user, analyst="admin")
    with pytest.raises(RuleViolation, match="you escalated yourself"):
        service.resolve(db, admin, case.id, case.version, service.APPROVED, "Fine")
    case = service.resolve(db, user("erin"), case.id, case.version, service.APPROVED, "Fine")
    assert case.status == service.APPROVED


def test_closed_cases_are_final(db, user):
    case = claimed_case(db, user)
    case = service.approve(db, user("dave"), case.id, case.version, "Good")
    with pytest.raises(InvalidTransition):
        service.claim(db, user("heidi"), case.id, case.version)
    with pytest.raises(InvalidTransition):
        service.reject(db, user("dave"), case.id, case.version, "Oops")


def test_release_returns_case_to_open_queue(db, user):
    case = claimed_case(db, user, "heidi")  # seed data already has a case in dave's queue
    assert [c.id for c in service.list_cases(db, user("heidi"), "mine")] == [case.id]
    case = service.release(db, user("heidi"), case.id, case.version)
    assert (case.status, case.assigned_to) == (service.OPEN, None)
    assert case.id in [c.id for c in service.list_cases(db, user("dave"), "open")]
    assert service.list_cases(db, user("heidi"), "mine") == []
    assert service.claim(db, user("dave"), case.id, case.version).assigned_to == "dave"


def test_intake_validates_input(db, user):
    erin = user("erin")
    base = dict(customer_name="C", date_of_birth=DOB, government_id=GOV_ID, country="GB")
    for bad in (
        {"date_of_birth": "21/04/1990"},
        {"date_of_birth": "2999-01-01"},
        {"country": "GBR"},
        {"government_id": " "},
    ):
        with pytest.raises(ValidationError):
            service.create_case(db, erin, **{**base, **bad}, document_status="UPLOADED")
    with pytest.raises(ValidationError):
        service.create_case(db, erin, **base, document_status="LOST")


# --- concurrency, audit, masking -------------------------------------------------------------


def test_stale_update_rejected(db, user, login):
    case = new_case(db, user)
    stale_version = case.version
    case = service.claim(db, user("dave"), case.id, stale_version)
    with pytest.raises(StaleWrite):
        service.approve(db, user("dave"), case.id, stale_version, "ok")
    response = login("dave").post(
        f"/kyc/{case.id}/approve", data={"version": stale_version, "reason": "ok"}
    )
    assert response.status_code == 409
    assert db.get(type(case), case.id).status == service.IN_REVIEW


def test_every_mutation_audited(db, user):
    case = new_case(db, user)
    case = service.claim(db, user("heidi"), case.id, case.version)
    case = service.release(db, user("heidi"), case.id, case.version)
    case = service.claim(db, user("dave"), case.id, case.version)
    case = service.escalate(db, user("dave"), case.id, case.version, "Address mismatch")
    case = service.resolve(db, user("erin"), case.id, case.version, service.APPROVED, "Verified")
    other = claimed_case(db, user)
    service.reject(db, user("dave"), other.id, other.version, "Expired passport")
    third = claimed_case(db, user)
    service.approve(db, user("dave"), third.id, third.version, "All good")

    events = audit.trail(db, service.ENTITY, case.id)
    assert [(e.action, e.actor, e.reason) for e in events] == [
        ("create", "erin", None),
        ("claim", "heidi", None),
        ("release", "heidi", None),
        ("claim", "dave", None),
        ("escalate", "dave", "Address mismatch"),
        ("resolve", "erin", "Verified"),
    ]
    assert events[-1].before["status"] == service.ESCALATED
    assert events[-1].after["status"] == service.APPROVED
    assert [(e.action, e.reason) for e in audit.trail(db, service.ENTITY, other.id)][-1] == (
        "reject",
        "Expired passport",
    )
    assert [(e.action, e.reason) for e in audit.trail(db, service.ENTITY, third.id)][-1] == (
        "approve",
        "All good",
    )


@pytest.mark.parametrize(
    ("field", "raw", "masked"),
    [("government_id", GOV_ID, "••••7766"), ("date_of_birth", DOB, "1990-••-••")],
)
def test_protected_field_masked_and_reveal_audited(db, user, login, field, raw, masked):
    case = claimed_case(db, user, "dave")
    client = login("dave")
    for url in ("/kyc", f"/kyc/{case.id}"):
        html = client.get(url).text
        assert raw not in html and masked in html

    url = f"/reveal/kyc_cases/{case.id}/{field}"
    assert client.post(url, data={"reason": ""}).status_code == 422
    response = client.post(url, data={"reason": "Matching ID against uploaded scan"})
    assert response.status_code == 200 and raw in response.text

    reveal = audit.trail(db, service.ENTITY, case.id)[-1]
    assert (reveal.action, reveal.actor, reveal.reason, reveal.after) == (
        "reveal",
        "dave",
        "Matching ID against uploaded scan",
        {"field": field},
    )
    create = audit.trail(db, service.ENTITY, case.id)[0]
    assert create.after[field] == masked  # audit never stores the raw value

    assert login("ivan").post(url, data={"reason": "Just checking it"}).status_code == 403
    assert login("erin").post(url, data={"reason": "Supervisor review"}).status_code == 200


def test_flash_and_trail_never_show_raw_values(db, user, login):
    case = claimed_case(db, user)
    client = login("dave")
    response = client.post(
        f"/kyc/{case.id}/escalate", data={"version": case.version, "reason": "Unsure"}
    )
    assert response.status_code == 200
    assert GOV_ID not in response.text and DOB not in response.text
    assert GOV_ID not in login("ivan").get("/audit").text


@pytest.mark.parametrize("field", ["government_id", "date_of_birth"])
def test_analyst_can_reveal_only_on_case_they_hold(db, user, login, field):
    def reveal(name, case):
        url = f"/reveal/kyc_cases/{case.id}/{field}"
        return login(name).post(url, data={"reason": "Checking against scan"}).status_code

    def has_reveal_button(name, case):
        return (
            f'hx-post="/reveal/kyc_cases/{case.id}/{field}"'
            in login(name).get(f"/kyc/{case.id}").text
        )

    case = new_case(db, user)
    assert reveal("dave", case) == 403 and not has_reveal_button("dave", case)  # OPEN
    case = service.claim(db, user("dave"), case.id, case.version)
    assert reveal("dave", case) == 200 and has_reveal_button("dave", case)
    assert reveal("heidi", case) == 403 and not has_reveal_button("heidi", case)
    assert reveal("erin", case) == 200 and has_reveal_button("erin", case)  # supervisor: any case

    case = service.escalate(db, user("dave"), case.id, case.version, "Unsure")
    assert reveal("dave", case) == 403  # no longer holds it
    assert reveal("erin", case) == 200

    released = claimed_case(db, user, "heidi")
    released = service.release(db, user("heidi"), released.id, released.version)
    assert reveal("heidi", released) == 403

    reveals = [e for e in audit.trail(db, service.ENTITY, case.id) if e.action == "reveal"]
    assert [e.actor for e in reveals] == ["dave", "erin", "erin"]  # denied attempts not logged


def test_can_reveal_pii_hook(db, user):
    case = new_case(db, user)
    assert service.can_reveal_pii(db, user("erin"), case)
    assert not service.can_reveal_pii(db, user("dave"), case)
    case = service.claim(db, user("dave"), case.id, case.version)
    assert service.can_reveal_pii(db, user("dave"), case)
    assert not service.can_reveal_pii(db, user("heidi"), case)
