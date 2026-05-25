from pathlib import Path

from fastapi.testclient import TestClient

from agentdrive.web.app import SESSION_COOKIE, create_app
from agentdrive.web.auth import AuthStore


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "auth.db")
    return TestClient(app, follow_redirects=False)


def test_first_run_creates_admin_and_session(tmp_path: Path):
    client = make_client(tmp_path)

    response = client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/setup"

    response = client.post(
        "/setup",
        data={"username": "admin", "password": "correct horse battery staple"},
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"
    assert SESSION_COOKIE in response.headers["set-cookie"]

    store = AuthStore(tmp_path / "auth.db")
    user = store.get_user_by_username("admin")
    assert user is not None
    assert user.role == "admin"


def test_signup_creates_pending_user_until_admin_approves(tmp_path: Path):
    client = make_client(tmp_path)
    client.post("/setup", data={"username": "admin", "password": "admin password 123"})

    response = client.post(
        "/signup",
        data={"username": "operator", "password": "operator password 123"},
    )
    assert response.status_code == 200
    assert "pending" in response.text.lower()

    response = client.post(
        "/login",
        data={"username": "operator", "password": "operator password 123"},
    )
    assert response.status_code == 401

    store = AuthStore(tmp_path / "auth.db")
    pending = store.get_user_by_username("operator")
    assert pending is not None
    assert pending.role == "pending"
    store.approve_user(pending.id)

    response = client.post(
        "/login",
        data={"username": "operator", "password": "operator password 123"},
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


def test_env_bootstrap_creates_admin(tmp_path: Path, monkeypatch):
    password_file = tmp_path / "admin-pass"
    password_file.write_text("bootstrap password 123\n", encoding="utf-8")
    monkeypatch.setenv("AGENTDRIVE_ADMIN_USERNAME", "headless")
    monkeypatch.setenv("AGENTDRIVE_ADMIN_PASSWORD_FILE", str(password_file))

    client = make_client(tmp_path)

    response = client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

    response = client.post(
        "/login",
        data={"username": "headless", "password": "bootstrap password 123"},
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


def test_signup_can_be_disabled(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client.post("/setup", data={"username": "admin", "password": "admin password 123"})

    monkeypatch.setenv("AGENTDRIVE_DISABLE_SIGNUP", "1")
    response = client.post(
        "/signup",
        data={"username": "operator", "password": "operator password 123"},
    )
    assert response.status_code == 403
    assert "disabled" in response.text.lower()
