from datetime import timedelta

import jwt
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.models import User
from tests.conftest import PASSWORD

ME = "/api/v1/auth/me"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"


def login(client: TestClient, email: str, password: str = PASSWORD):
    return client.post(LOGIN, json={"email": email, "password": password})


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- login ---------------------------------------------------------------


def test_login_ok_returns_tokens_and_me_works(client: TestClient, users: dict[str, User]) -> None:
    r = login(client, "admin@t.test")
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_expires_in"] == settings.access_token_minutes * 60

    me = client.get(ME, headers=bearer(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "admin@t.test"
    assert me.json()["role"] == "admin"
    assert me.json()["institution"] is None


def test_login_email_is_case_insensitive(client: TestClient, users: dict[str, User]) -> None:
    assert login(client, "  Admin@T.test ").status_code == 200


def test_me_includes_institution_for_institution_user(
    client: TestClient, users: dict[str, User]
) -> None:
    token = login(client, "inst@t.test").json()["access_token"]
    inst = client.get(ME, headers=bearer(token)).json()["institution"]
    assert inst["code"] == "TST"


def test_login_wrong_password(client: TestClient, users: dict[str, User]) -> None:
    r = login(client, "admin@t.test", "nope")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


def test_login_unknown_email_same_error(client: TestClient, users: dict[str, User]) -> None:
    r = login(client, "nobody@t.test")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


def test_login_inactive_user_rejected(client: TestClient, users: dict[str, User]) -> None:
    assert login(client, "gone@t.test").status_code == 401


# --- refresh -------------------------------------------------------------


def test_refresh_returns_working_access_token(client: TestClient, users: dict[str, User]) -> None:
    refresh_token = login(client, "verifier@t.test").json()["refresh_token"]
    r = client.post(REFRESH, json={"refresh_token": refresh_token})
    assert r.status_code == 200
    me = client.get(ME, headers=bearer(r.json()["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "verifier@t.test"


def test_refresh_rejects_access_token(client: TestClient, users: dict[str, User]) -> None:
    access = login(client, "verifier@t.test").json()["access_token"]
    r = client.post(REFRESH, json={"refresh_token": access})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


def test_refresh_rejects_expired_refresh_token(client: TestClient, users: dict[str, User]) -> None:
    u = users["verifier"]
    expired = create_refresh_token(u.id, u.role, expires_delta=timedelta(seconds=-1))
    r = client.post(REFRESH, json={"refresh_token": expired})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "token_expired"


def test_refresh_rejected_for_deactivated_user(
    client: TestClient, users: dict[str, User], db
) -> None:
    refresh_token = login(client, "verifier@t.test").json()["refresh_token"]
    users["verifier"].is_active = False
    db.flush()
    assert client.post(REFRESH, json={"refresh_token": refresh_token}).status_code == 401


# --- invalid / expired access tokens ------------------------------------


def test_me_without_token(client: TestClient) -> None:
    r = client.get(ME)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "not_authenticated"


def test_me_with_expired_token(client: TestClient, users: dict[str, User]) -> None:
    u = users["admin"]
    token = create_access_token(u.id, u.role, expires_delta=timedelta(seconds=-1))
    r = client.get(ME, headers=bearer(token))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "token_expired"


def test_me_with_garbage_token(client: TestClient) -> None:
    r = client.get(ME, headers=bearer("not.a.jwt"))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


def test_me_with_wrong_signature(client: TestClient, users: dict[str, User]) -> None:
    u = users["admin"]
    forged = jwt.encode(
        {"sub": str(u.id), "role": "admin", "type": "access", "exp": 9_999_999_999},
        "some-other-secret",
        algorithm="HS256",
    )
    r = client.get(ME, headers=bearer(forged))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


def test_me_rejects_refresh_token(client: TestClient, users: dict[str, User]) -> None:
    refresh_token = login(client, "admin@t.test").json()["refresh_token"]
    assert client.get(ME, headers=bearer(refresh_token)).status_code == 401


# --- role blocking -------------------------------------------------------


def test_admin_can_access_admin_route(client: TestClient, users: dict[str, User]) -> None:
    token = login(client, "admin@t.test").json()["access_token"]
    assert client.get("/_test/admin-only", headers=bearer(token)).status_code == 200


def test_verifier_blocked_from_admin_route(client: TestClient, users: dict[str, User]) -> None:
    token = login(client, "verifier@t.test").json()["access_token"]
    r = client.get("/_test/admin-only", headers=bearer(token))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_institution_blocked_from_admin_route(client: TestClient, users: dict[str, User]) -> None:
    token = login(client, "inst@t.test").json()["access_token"]
    assert client.get("/_test/admin-only", headers=bearer(token)).status_code == 403


def test_admin_route_requires_auth(client: TestClient) -> None:
    assert client.get("/_test/admin-only").status_code == 401
