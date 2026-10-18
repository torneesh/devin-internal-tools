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


def seed(db: Session, fake_data: bool = False) -> None:
    if db.scalar(select(func.count()).select_from(User)):
        return
    for username, display_name, roles in USERS:
        db.add(User(username=username, display_name=display_name, roles=list(roles)))
    db.commit()
    seed_refunds(db)
    seed_kyc(db)
    seed_flags(db)
    if fake_data:
        seed_fake(db)


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


def seed_fake(db: Session, n_refunds: int = 45, n_cases: int = 35) -> None:
    """Bulk fake records (Faker, fixed seed) created through the services, so every row has a
    real audit trail and passed the same rules as a user action. All identities are fake."""
    import random

    from faker import Faker

    from tools.flags import service as flags
    from tools.kyc import service as kyc
    from tools.refunds import service as refunds

    rng = random.Random(42)
    Faker.seed(42)
    fake = Faker(["en_GB", "de_DE", "fr_FR", "it_IT", "es_ES", "nl_NL"])
    u = {name: load_user(db, name) for name, _, _ in USERS}
    reasons = [
        "Charged twice for the same order",
        "Order cancelled before shipping",
        "Item never arrived",
        "Subscription cancelled within cooling-off period",
        "Service outage credit",
        "Duplicate card authorisation captured",
        "Fee charged in error",
    ]

    for i in range(n_refunds):
        large = rng.random() < 0.3
        r = refunds.create_refund(
            db,
            u["alice"],
            txn_id=f"TXN-{11000 + i}",
            customer_name=fake.name(),
            bank_account=fake.iban(),
            amount_cents=rng.randint(120_000, 900_000) if large else rng.randint(500, 95_000),
            reason=rng.choice(reasons),
        )
        outcome = rng.choices(
            ["requested", "half", "approved", "rejected", "paid", "failed", "unknown"],
            weights=[5, 2 if large else 0, 3, 2, 8, 1, 1],
        )[0]
        if outcome == "requested":
            continue
        if outcome == "rejected":
            refunds.reject(db, u["bob"], r.id, r.version, "Outside refund policy window")
            continue
        r = refunds.approve(db, u["bob"], r.id, r.version)
        if outcome == "half":
            continue
        if large:
            r = refunds.approve(db, u["carol"], r.id, r.version)
        if outcome == "approved":
            continue
        mode = {"failed": "fail", "unknown": "timeout_after_accept"}.get(outcome, "ok")
        r = refunds.set_provider_mode(db, u["bob"], r.id, r.version, mode)
        refunds.execute(db, u["carol"] if large else u["bob"], r.id, r.version)

    docs = [kyc.DOC_UPLOADED] * 6 + [kyc.DOC_MISSING, kyc.DOC_UNREADABLE]
    for _ in range(n_cases):
        locale = rng.choice(fake.locales)
        f = fake[locale]
        case = kyc.create_case(
            db,
            u["erin"],
            customer_name=f.name(),
            date_of_birth=f.date_of_birth(minimum_age=18, maximum_age=80).isoformat(),
            government_id=f.bothify("??#######").upper(),
            country=locale.split("_")[1],
            document_status=rng.choice(docs),
        )
        outcome = rng.choices(
            ["open", "review", "escalated", "approved", "rejected", "resolved"],
            weights=[8, 4, 3, 10, 3, 2],
        )[0]
        if outcome == "open":
            continue
        analyst = u[rng.choice(["dave", "heidi"])]
        case = kyc.claim(db, analyst, case.id, case.version)
        if outcome == "review":
            continue
        if outcome == "approved" and case.document_status == kyc.DOC_UPLOADED:
            kyc.approve(db, analyst, case.id, case.version, "ID and selfie match; sanctions clear")
        elif outcome in ("approved", "rejected"):
            kyc.reject(db, analyst, case.id, case.version, "Documents do not match application")
        else:
            case = kyc.escalate(db, analyst, case.id, case.version, "Possible sanctions match")
            if outcome == "resolved":
                kyc.resolve(
                    db, u["erin"], case.id, case.version, kyc.REJECTED, "Confirmed sanctions hit"
                )

    for key, description in [
        ("payments.3ds-v2", "3-D Secure 2 challenge flow"),
        ("payments.instant-payouts", "Instant payouts to debit cards"),
        ("onboarding.selfie-check", "Liveness check during onboarding"),
        ("onboarding.address-autocomplete", "Address autocomplete on sign-up"),
        ("cards.virtual-cards", "Issue virtual cards in-app"),
        ("cards.spend-limits", "Per-card spend limits"),
        ("ledger.async-posting", "Post ledger entries asynchronously"),
        ("fraud.velocity-rules-v3", "New transaction velocity rules"),
        ("support.chat-handoff", "Bot-to-agent chat handoff"),
        ("billing.annual-plans", "Annual billing option"),
    ]:
        flag = flags.create_flag(db, u["frank"], key=key, description=description)
        if rng.random() < 0.7:
            state = flags.set_enabled(
                db, u["frank"], flag.id, "staging", flag.state("staging").version, True
            )
            flags.set_rollout(db, u["frank"], flag.id, "staging", state.version, 100)
        if rng.random() < 0.4:
            state = flags.set_enabled(
                db, u["grace"], flag.id, "production", flag.state("production").version, True
            )
            pct = rng.choice([5, 10, 25, 50, 100])
            flags.set_rollout(db, u["grace"], flag.id, "production", state.version, pct)
