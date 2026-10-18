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
