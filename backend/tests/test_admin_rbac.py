import uuid

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.models.enums import UserRole
from app.models.user import User


def test_admin_routes_reject_unauthenticated_requests():
    client = TestClient(app)
    response = client.get("/api/admin/users")
    assert response.status_code == 401


def test_admin_routes_reject_regular_users():
    fake_user = User(id=uuid.uuid4(), email="user@test.com", role=UserRole.USER, is_active=True, is_suspended=False)
    app.dependency_overrides[get_current_user] = lambda: fake_user
    try:
        client = TestClient(app)
        response = client.get("/api/admin/users")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_admin_routes_pass_rbac_for_admin_users():
    """Confirms an admin clears the RBAC check and reaches the route body
    (a 500 here — from the DB connection failing since no Postgres exists
    in this test environment — is expected and still proves RBAC passed;
    a 403 would mean RBAC incorrectly blocked a real admin)."""
    fake_admin = User(id=uuid.uuid4(), email="admin@test.com", role=UserRole.ADMIN, is_active=True, is_suspended=False)
    app.dependency_overrides[get_current_user] = lambda: fake_admin
    try:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/admin/analytics")
        assert response.status_code != 403
        assert response.status_code != 401
    finally:
        app.dependency_overrides.clear()
