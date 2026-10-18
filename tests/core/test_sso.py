import pytest
from fastapi.testclient import TestClient

from app import create_app
from core import audit
from core.auth import load_user
from core.sso import SsoConfig, provision

ISSUER = "https://idp.example/realms/internal-tools"


@pytest.fixture
def sso_client():
    config = SsoConfig(ISSUER, "internal-tools", "secret", f"{ISSUER}/.well-known/x")
    with TestClient(create_app("sqlite://", fake_data=False, sso_config=config)) as c:
        yield c


def test_sso_provisions_user_with_roles_from_groups(db):
    claims = {"sub": "1", "preferred_username": "zoe", "name": "Zoe", "groups": ["auditor"]}
    user = provision(db, claims, ISSUER)
    assert user.roles == {"auditor"} and load_user(db, "zoe").display_name == "Zoe"
    event = audit.search(db, entity="users", actor="zoe")[0]
    assert event.action == "login" and event.after == {"roles": ["auditor"]}


def test_group_change_in_idp_changes_roles_and_is_audited(db):
    claims = {"sub": "2", "preferred_username": "bob", "groups": ["auditor"]}
    assert provision(db, claims, ISSUER).roles == {"auditor"}
    event = audit.search(db, entity="users", actor="bob")[0]
    assert event.before == {"roles": ["refund_approver"]} and event.after == {"roles": ["auditor"]}


def test_user_switcher_disabled_when_sso_on(sso_client):
    page = sso_client.get("/login").text
    assert "Sign in with SSO" in page and 'name="username"' not in page
    response = sso_client.post("/login", data={"username": "admin"}, follow_redirects=False)
    assert response.status_code == 403
    assert sso_client.get("/", follow_redirects=False).headers["location"] == "/login"


def test_logout_goes_through_idp_when_sso_on(sso_client):
    response = sso_client.post("/logout", follow_redirects=False)
    assert response.headers["location"] == "/auth/logout"
