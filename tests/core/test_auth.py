from core import audit


def test_unauthenticated_redirects_to_login(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/login"


def test_user_switch_changes_identity_and_tools(login):
    client = login("alice")
    home = client.get("/").text
    assert "Alice (Support)" in home
    assert '<a href="/refunds">Refunds</a>' in home
    home = login("frank").get("/").text
    assert "Frank (Engineer)" in home
    assert '<a href="/refunds">Refunds</a>' not in home


def test_require_role_forbids_and_allows(login):
    assert login("alice").get("/audit").status_code == 403
    assert login("ivan").get("/audit").status_code == 200
    assert login("admin").get("/audit").status_code == 200


def test_login_is_audited(login, db):
    login("dave")
    assert audit.search(db, entity="users", actor="dave")[0].action == "login"


def test_open_redirect_blocked(client):
    response = client.post(
        "/login", data={"username": "bob", "next": "//evil.example"}, follow_redirects=False
    )
    assert response.headers["location"] == "/"
