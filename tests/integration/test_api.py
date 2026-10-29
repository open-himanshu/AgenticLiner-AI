"""
Integration tests for FastAPI application endpoints using modern httpx ASGI transport.
"""
import pytest
import httpx
from backend.api.main import app

@pytest.mark.anyio
async def test_page_routes():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        # First verify login page is available
        login_resp = await ac.get("/login")
        assert login_resp.status_code == 200
        assert "Sign In" in login_resp.text

        # Authenticate as supervisor to test protected pages
        auth_resp = await ac.post("/login", data={"email": "admin@galgotias.edu", "password": "Admin@123"})
        assert auth_resp.status_code in (200, 302)

        response = await ac.get("/autopilot")
        assert response.status_code == 200
        assert "Autopilot" in response.text

        response = await ac.get("/schedule")
        assert response.status_code == 200
        assert "OR-Tools" in response.text

        response = await ac.get("/analytics")
        assert response.status_code == 200

@pytest.mark.anyio
async def test_api_catalog():
    from backend.core.database.connection import execute_query
    execute_query("INSERT OR IGNORE INTO resources (id, category, name, stock) VALUES ('res_test', 'equipment', 'Mic Set', 10)")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/catalog")
        assert response.status_code == 200
        data = response.json()
        assert "catalog" in data
        assert len(data["catalog"]) > 0

@pytest.mark.anyio
async def test_api_schedule_solver():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/schedule/solve", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["schedule"]) > 0

@pytest.mark.anyio
async def test_hero_speaker_cancellation():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/schedule/hero-speaker-cancel")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "re_planned"
        assert data["substitute_allocated"] == "Dr. Neha Verma (School of AI)"
        assert len(data["new_schedule"]) > 0

@pytest.mark.anyio
async def test_api_feedback_submission():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/feedback/submit", json={
            "event_id": "ev_001",
            "rating": 5,
            "comment": "The hands-on coding session was outstanding and very insightful!"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "saved"
        assert data["analysis"]["sentiment"] == "positive"
        assert "content" in data["themes"]
