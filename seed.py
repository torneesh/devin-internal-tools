"""Users, roles and demo data. Loaded on startup when the database is empty."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.auth import User, load_user

ROLES = [
    "support_agent",
    "refund_approver",
    "kyc_analyst",
    "kyc_supervisor",
    "engineer",
    "release_manager",
    "auditor",
]

USERS = [
    ("alice", "Alice (Support)", ["support_agent"]),
    ("bob", "Bob (Refund approver)", ["refund_approver"]),
    ("carol", "Carol (Refund approver)", ["refund_approver"]),
    ("dave", "Dave (KYC analyst)", ["kyc_analyst"]),
    ("erin", "Erin (KYC supervisor)", ["kyc_supervisor"]),
    ("frank", "Frank (Engineer)", ["engineer"]),
    ("grace", "Grace (Release manager)", ["release_manager"]),
    ("heidi", "Heidi (KYC analyst)", ["kyc_analyst"]),
    ("ivan", "Ivan (Auditor)", ["auditor"]),
    ("admin", "Admin", ROLES),
]


def seed(db: Session) -> None:
    if db.scalar(select(func.count()).select_from(User)):
        return
    for username, display_name, roles in USERS:
        db.add(User(username=username, display_name=display_name, roles=list(roles)))
    db.commit()
    seed_refunds(db)
    seed_kyc(db)
    seed_flags(db)


def seed_refunds(db: Session) -> None:
    from tools.refunds import service

    alice, bob = load_user(db, "alice"), load_user(db, "bob")
    service.create_refund(
        db,
        alice,
        txn_id="TXN-10021",
        customer_name="Maya Patel",
        bank_account="GB29NWBK60161331926819",
        amount_cents=4_500,
        reason="Charged twice for the same order",
    )
    service.create_refund(
        db,
        alice,
        txn_id="TXN-10388",
        customer_name="Jonas Weber",
        bank_account="DE89370400440532013000",
        amount_cents=240_000,
        reason="Service outage credit (enterprise plan)",
    )
    ready = service.create_refund(
        db,
        alice,
        txn_id="TXN-10412",
        customer_name="Ana Souza",
        bank_account="FR1420041010050500013M02606",
        amount_cents=12_000,
        reason="Order cancelled before shipping",
    )
    service.approve(db, bob, ready.id, ready.version)


def seed_kyc(db: Session) -> None:
    from tools.kyc import service

    dave, erin = load_user(db, "dave"), load_user(db, "erin")
    cases = [
        ("Liam O'Connor", "1988-03-14", "PA1234567", "IE", "UPLOADED"),
        ("Sofia Rossi", "1992-11-02", "YA9876543", "IT", "UPLOADED"),
        ("Kenji Tanaka", "1979-07-30", "TK5550123", "JP", "UNREADABLE"),
        ("Amara Okafor", "2001-01-19", "A08812345", "NG", "MISSING"),
        ("Lucas Martin", "1985-05-05", "18AB76543", "FR", "UPLOADED"),
    ]
    created = [
        service.create_case(
            db,
            erin,
            customer_name=name,
            date_of_birth=dob,
            government_id=gov_id,
            country=country,
            document_status=docs,
        )
        for name, dob, gov_id, country, docs in cases
    ]
    service.claim(db, dave, created[1].id, created[1].version)  # stays in dave's queue
    escalated = service.claim(db, dave, created[2].id, created[2].version)
    service.escalate(
        db, dave, escalated.id, escalated.version, "Passport scan unreadable; possible tampering"
    )
    done = service.claim(db, dave, created[4].id, created[4].version)
    service.approve(db, dave, done.id, done.version, "ID and selfie match; sanctions check clear")


def seed_flags(db: Session) -> None:
    from tools.flags import service

    frank, grace = load_user(db, "frank"), load_user(db, "grace")

    def change(fn, flag, env, *args):
        state = flag.state(env)
        return fn(db, frank if env == "staging" else grace, flag.id, env, state.version, *args)

    checkout = service.create_flag(
        db, frank, key="checkout.new-flow", description="Single-page checkout redesign"
    )
    change(service.set_enabled, checkout, "staging", True)
    change(service.set_rollout, checkout, "staging", 50)
    change(service.set_rollout, checkout, "staging", 100)
    change(service.set_enabled, checkout, "production", True)
    change(service.set_rollout, checkout, "production", 10)
    change(service.set_rollout, checkout, "production", 25)

    search = service.create_flag(
        db, frank, key="search.semantic-ranking", description="Embedding-based search ranking"
    )
    change(service.set_enabled, search, "staging", True)
    change(service.set_rollout, search, "staging", 100)

    service.create_flag(
        db, frank, key="payments.retry-v2", description="New retry policy for card payments"
    )
