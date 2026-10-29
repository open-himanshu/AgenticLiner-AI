"""
Automated Pytest Suite for Authentication, Strong Password Policy, OTP Verification, and Role-Based Access Control (RBAC).
"""

import pytest
import httpx
import uuid
from backend.api.main import app
from backend.services.auth_service import (
    hash_password,
    verify_password,
    authenticate_user,
    validate_strong_password,
    create_otp,
    verify_otp,
    get_user_by_email
)
from backend.services.seed_users import seed_users

@pytest.fixture(autouse=True)
def setup_users():
    seed_users(force=True)

def test_password_hashing():
    raw_pass = "SecurePass@2026"
    h1 = hash_password(raw_pass)
    assert h1 != raw_pass
    assert verify_password(raw_pass, h1) is True
    assert verify_password("WrongPass", h1) is False

def test_strong_password_policy():
    valid, _ = validate_strong_password("GoodPass@123")
    assert valid is True

    # Too short
    valid, err = validate_strong_password("Sh@1")
    assert valid is False
    assert "8 characters" in err

    # Missing uppercase
    valid, err = validate_strong_password("lowercase@123")
    assert valid is False
    assert "uppercase" in err

    # Missing lowercase
    valid, err = validate_strong_password("UPPERCASE@123")
    assert valid is False
    assert "lowercase" in err

    # Missing number
    valid, err = validate_strong_password("NoNumber@Pass")
    assert valid is False
    assert "number" in err

    # Missing special character
    valid, err = validate_strong_password("NoSymbol12345")
    assert valid is False
    assert "special symbol" in err

def test_authenticate_user_service():
    user, err = authenticate_user("admin@galgotias.edu", "Admin@123")
    assert user is not None
    assert err is None
    assert user["role"] == "supervisor"
    assert "password_hash" not in user

    user_bad, err_bad = authenticate_user("admin@galgotias.edu", "WrongPassword")
    assert user_bad is None
    assert "Invalid email or password" in err_bad

    user_missing, err_missing = authenticate_user("nonexistent@galgotias.edu", "AnyPass")
    assert user_missing is None
    assert "Invalid email or password" in err_missing

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

@pytest.mark.anyio
async def test_signup_otp_and_verification_flow():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        # 1. Submit signup form with strong password
        new_email = "new.faculty@galgotias.edu"
        res = await client.post(
            "/signup",
            data={
                "full_name": "Dr. Sunita Rao",
                "email": new_email,
                "role": "organiser",
                "department": "School of AI",
                "password": "FacultyPass@123",
                "confirm_password": "FacultyPass@123"
            },
            headers={"Accept": "text/html"}
        )
        assert res.status_code == 302
        assert "/verify-otp" in res.headers["location"]
        
        # Extract demo_code from location
        loc = res.headers["location"]
        import urllib.parse
        parsed = urllib.parse.urlparse(loc)
        params = urllib.parse.parse_qs(parsed.query)
        otp_code = params.get("demo_code", [""])[0]
        assert len(otp_code) == 6

        # 2. Test wrong OTP rejection
        res_fail = await client.post(
            "/verify-otp",
            data={"email": new_email, "purpose": "signup", "otp_code": "000000"}
        )
        assert res_fail.status_code == 200
        assert "Incorrect verification code" in res_fail.text

        # 3. Test correct OTP verification & auto-login
        res_ok = await client.post(
            "/verify-otp",
            data={"email": new_email, "purpose": "signup", "otp_code": otp_code}
        )
        assert res_ok.status_code == 302
        assert res_ok.headers["location"] == "/organiser"

        # 4. Confirm newly registered user can access /organiser
        res_dashboard = await client.get("/organiser")
        assert res_dashboard.status_code == 200
        assert "Dr. Sunita Rao" in res_dashboard.text

@pytest.mark.anyio
async def test_signup_weak_password_rejected():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        res = await client.post(
            "/signup",
            data={
                "full_name": "Weak Pass User",
                "email": "weak@galgotias.edu",
                "role": "participant",
                "department": "CSE",
                "password": "weak",
                "confirm_password": "weak"
            },
            headers={"Accept": "text/html"}
        )
        assert res.status_code == 200
        assert "at least 8 characters" in res.text

@pytest.mark.anyio
async def test_forgot_and_reset_password_flow():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        target_email = "student@galgotias.edu"
        # 1. Request password reset OTP
        res = await client.post("/forgot-password", data={"email": target_email})
        assert res.status_code == 302
        assert "/verify-otp" in res.headers["location"]

        import urllib.parse
        parsed = urllib.parse.urlparse(res.headers["location"])
        params = urllib.parse.parse_qs(parsed.query)
        otp_code = params.get("demo_code", [""])[0]
        assert len(otp_code) == 6

        # 2. Verify OTP
        res_verify = await client.post(
            "/verify-otp",
            data={"email": target_email, "purpose": "password_reset", "otp_code": otp_code}
        )
        assert res_verify.status_code == 302
        assert "/reset-password" in res_verify.headers["location"]

        # 3. Submit new strong password
        new_pass = "StudentNewPass@456"
        res_reset = await client.post(
            "/reset-password",
            data={
                "email": target_email,
                "new_password": new_pass,
                "confirm_password": new_pass
            }
        )
        assert res_reset.status_code == 302
        assert "/login?reset_success=1" in res_reset.headers["location"]

        # 4. Test login with the newly set password
        res_login = await client.post(
            "/login",
            data={"email": target_email, "password": new_pass},
            headers={"Accept": "text/html"}
        )
        assert res_login.status_code == 302
        assert res_login.headers["location"] == "/participant"

@pytest.mark.anyio
async def test_google_auth_fast_login_and_role_access():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        # Sign in with Google as an Organiser
        res = await client.post(
            "/auth/google",
            json={
                "demo_google": True,
                "email": "prof.sharma.google@galgotias.edu",
                "name": "Prof. Sharma",
                "role": "organiser",
                "department": "Computer Science (CSE)"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["redirect_url"] == "/organiser"
        assert data["user"]["email"] == "prof.sharma.google@galgotias.edu"
        assert data["user"]["role"] == "organiser"

        # Verify session cookie was issued and can access /organiser
        res_dash = await client.get("/organiser")
        assert res_dash.status_code == 200
        assert "Prof. Sharma" in res_dash.text

@pytest.mark.anyio
async def test_email_service_safety():
    from backend.services.email_service import is_smtp_configured, send_email_otp
    # In test environment without SMTP credentials, is_smtp_configured returns False
    # and send_email_otp safely returns False without raising unhandled exceptions
    ok, err = send_email_otp("test@galgotias.edu", "123456", "signup")
    if not is_smtp_configured():
        assert ok is False
        assert "SMTP is not configured" in err

