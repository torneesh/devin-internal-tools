"""Shared pytest fixtures for platform and tool tests."""

import pytest
from fastapi.testclient import TestClient

from app import create_app
from core.auth import load_user


@pytest.fixture
def app():
    """A fresh app on an in-memory database, seeded, with every tool (and _template) mounted."""
    return create_app("sqlite://", include_template=True, fake_data=False)


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db(app):
    session = app.state.SessionLocal()
    yield session
    session.close()


@pytest.fixture
def user(db):
    """user("bob") -> CurrentUser, for calling service functions directly."""
    return lambda username: load_user(db, username)


@pytest.fixture
def login(client):
    """login("bob") signs the test client in as bob (mock SSO) and returns it."""

    def _login(username: str) -> TestClient:
        response = client.post("/login", data={"username": username}, follow_redirects=False)
        assert response.status_code == 303
        return client

    return _login
