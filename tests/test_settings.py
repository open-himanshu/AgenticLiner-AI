import pytest
import httpx
from backend.api.main import app
from backend.services.auth_service import (
    get_user_by_email,
    change_user_password
)
from backend.services.seed_users import seed_users

@pytest.fixture(autouse=True)
def setup_users():
    seed_users(force=True)

@pytest.mark.anyio
async def test_settings_requires_login():
    """Unauthenticated access should redirect to /login."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        res = await client.get("/settings")
        assert res.status_code == 302
        assert "/login" in res.headers["location"]

@pytest.mark.anyio
async def test_authenticated_settings_page():
    """Authenticated user should be able to view /settings."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        # Login as student
        login_res = await client.post(
            "/login",
            data={"email": "student@galgotias.edu", "password": "Student@123"},
            headers={"Accept": "text/html"}
        )
        assert login_res.status_code == 302

        # Visit settings
        res = await client.get("/settings")
        assert res.status_code == 200
        assert "Account &amp; Profile Settings" in res.text or "Account & Profile Settings" in res.text
        assert "student@galgotias.edu" in res.text

@pytest.mark.anyio
async def test_update_user_profile_flow():
    """Tests updating personal details via /settings/profile."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        # Login as organiser
        await client.post(
            "/login",
            data={"email": "organiser@galgotias.edu", "password": "Organiser@123"},
            headers={"Accept": "text/html"}
        )

        # Update profile
        update_res = await client.post(
            "/settings/profile",
            data={
                "full_name": "Organiser Lead Updated",
                "department": "Technojam Club",
                "phone": "+91 99999 88888",
                "bio": "Lead coordinator for Hackathons"
            }
        )
        assert update_res.status_code == 302
        assert "success=" in update_res.headers["location"]

        # Verify user record in DB
        user = get_user_by_email("organiser@galgotias.edu")
        assert user["full_name"] == "Organiser Lead Updated"
        assert user["department"] == "Technojam Club"
        assert user["phone"] == "+91 99999 88888"
        assert user["bio"] == "Lead coordinator for Hackathons"

@pytest.mark.anyio
async def test_change_password_policy_and_verification():
    """Tests changing password with correct and incorrect current passwords."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        # Login as student
        await client.post(
            "/login",
            data={"email": "student@galgotias.edu", "password": "Student@123"},
            headers={"Accept": "text/html"}
        )

        # 1. Wrong current password
        fail_res = await client.post(
            "/settings/change-password",
            data={
                "current_password": "WrongPassword123!",
                "new_password": "NewStrongPass@2026",
                "confirm_password": "NewStrongPass@2026"
            }
        )
        assert fail_res.status_code == 302
        assert "error=" in fail_res.headers["location"]

        # 2. Weak new password
        weak_res = await client.post(
            "/settings/change-password",
            data={
                "current_password": "Student@123",
                "new_password": "weak",
                "confirm_password": "weak"
            }
        )
        assert weak_res.status_code == 302
        assert "error=" in weak_res.headers["location"]

        # 3. Successful change
        success_res = await client.post(
            "/settings/change-password",
            data={
                "current_password": "Student@123",
                "new_password": "Student@Updated2026!",
                "confirm_password": "Student@Updated2026!"
            }
        )
        assert success_res.status_code == 302
        assert "success=" in success_res.headers["location"]

        # 4. Verify login with new password
        new_login = await client.post(
            "/login",
            data={"email": "student@galgotias.edu", "password": "Student@Updated2026!"},
            headers={"Accept": "text/html"}
        )
        assert new_login.status_code == 302

@pytest.mark.anyio
async def test_update_preferences_flow():
    """Tests updating language and notification preferences."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        # Login as supervisor
        await client.post(
            "/login",
            data={"email": "admin@galgotias.edu", "password": "Admin@123"},
            headers={"Accept": "text/html"}
        )

        pref_res = await client.post(
            "/settings/preferences",
            data={
                "preferred_language": "hinglish",
                "notifications_enabled": "on"
            }
        )
        assert pref_res.status_code == 302
        assert "success=" in pref_res.headers["location"]

        u = get_user_by_email("admin@galgotias.edu")
        assert u["preferred_language"] == "hinglish"
        assert u["notifications_enabled"] == 1
