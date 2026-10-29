"""
Automated Pytest Suite for Authentication and Role-Based Access Control (RBAC).
Verifies:
1. Password hashing with bcrypt.
2. Login with valid credentials and role-based redirect.
3. Login rejection on invalid password.
4. Unauthenticated access denial (redirect to /login).
5. Cross-role access control enforcement (403 Forbidden on unauthorized dashboards).
6. Safe session logout.
"""

import pytest
import httpx
from backend.api.main import app
from backend.services.auth_service import hash_password, verify_password, authenticate_user
from backend.services.seed_users import seed_users

@pytest.fixture(scope="module", autouse=True)
def setup_users():
    seed_users(force=False)

def test_password_hashing():
    raw_pass = "SecurePass@2026"
    h1 = hash_password(raw_pass)
    assert h1 != raw_pass
    assert verify_password(raw_pass, h1) is True
    assert verify_password("WrongPass", h1) is False

def test_authenticate_user_service():
    user = authenticate_user("admin@galgotias.edu", "Admin@123")
    assert user is not None
    assert user["role"] == "supervisor"
    assert "password_hash" not in user

    user_bad = authenticate_user("admin@galgotias.edu", "WrongPassword")
    assert user_bad is None

    user_missing = authenticate_user("nonexistent@galgotias.edu", "AnyPass")
    assert user_missing is None

@pytest.mark.anyio
async def test_unauthenticated_access_redirects():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        # Root redirects to /login when not authenticated
        res = await client.get("/")
        assert res.status_code == 302
        assert "/login" in res.headers["location"]

        # Protected supervisor route redirects to /login for HTML requests
        res = await client.get("/supervisor", headers={"Accept": "text/html"})
        assert res.status_code == 302
        assert "/login" in res.headers["location"]

@pytest.mark.anyio
async def test_login_invalid_credentials():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        res = await client.post(
            "/login",
            data={"email": "admin@galgotias.edu", "password": "WrongPassword"},
            headers={"Accept": "text/html"}
        )
        assert res.status_code == 200
        assert "Invalid email or password" in res.text

@pytest.mark.anyio
async def test_supervisor_login_and_access():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        # Login as supervisor
        res = await client.post(
            "/login",
            data={"email": "admin@galgotias.edu", "password": "Admin@123"},
            headers={"Accept": "text/html"}
        )
        assert res.status_code == 302
        assert res.headers["location"] == "/supervisor"

        # Now client has session cookie in jar, can access supervisor
        res = await client.get("/supervisor")
        assert res.status_code == 200
        assert "University Supervisor Dashboard" in res.text

@pytest.mark.anyio
async def test_cross_role_access_forbidden():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        # Login as organiser
        res = await client.post(
            "/login",
            data={"email": "organiser@galgotias.edu", "password": "Organiser@123"},
            headers={"Accept": "text/html"}
        )
        assert res.status_code == 302
        assert res.headers["location"] == "/organiser"

        # Organiser can access their own dashboard
        res = await client.get("/organiser")
        assert res.status_code == 200

        # Organiser trying to access supervisor dashboard MUST receive 403 Forbidden
        res = await client.get("/supervisor", headers={"Accept": "text/html"})
        assert res.status_code == 403
        assert "403" in res.text or "Forbidden" in res.text

        # Organiser trying to access data-manager dashboard MUST receive 403 Forbidden
        res = await client.get("/data-manager", headers={"Accept": "text/html"})
        assert res.status_code == 403

@pytest.mark.anyio
async def test_data_manager_login_and_cross_role_blocked():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        # Login as data manager
        res = await client.post(
            "/login",
            data={"email": "datamanager@galgotias.edu", "password": "Data@123"},
            headers={"Accept": "text/html"}
        )
        assert res.status_code == 302
        assert res.headers["location"] == "/data-manager"

        # Access data-manager
        res = await client.get("/data-manager")
        assert res.status_code == 200
        assert "Campus Data Operations Manager" in res.text

        # Data manager blocked from supervisor
        res = await client.get("/supervisor", headers={"Accept": "text/html"})
        assert res.status_code == 403

@pytest.mark.anyio
async def test_logout():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        # Login as student
        await client.post("/login", data={"email": "student@galgotias.edu", "password": "Student@123"})
        res = await client.get("/participant")
        assert res.status_code == 200

        # Logout
        res = await client.get("/logout")
        assert res.status_code == 302
        assert "/login" in res.headers["location"]

        # Subsequent access is redirected to login
        res = await client.get("/participant", headers={"Accept": "text/html"})
        assert res.status_code == 302
        assert "/login" in res.headers["location"]
