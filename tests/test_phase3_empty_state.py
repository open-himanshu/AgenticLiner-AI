"""
Automated Pytest Suite for Phase 3:
Purge Dummy Data, Real Zero-Counts, Helpful Empty States, and Admin Reset Data Action.
"""

import pytest
import httpx
from backend.api.main import app
from backend.services.admin_service import reset_all_operational_data
from backend.services.seed_users import seed_users
from backend.core.database.connection import fetch_one

@pytest.fixture(autouse=True)
def ensure_clean_zero_state():
    reset_all_operational_data("admin@galgotias.edu")

@pytest.mark.anyio
async def test_supervisor_dashboard_zero_counts_and_empty_state():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        # Login as supervisor
        login_res = await client.post("/login", data={"email": "admin@galgotias.edu", "password": "Admin@123"})
        assert login_res.status_code == 302
        assert login_res.headers["location"] == "/supervisor"

        res = await client.get("/supervisor")
        assert res.status_code == 200
        html = res.text

        # Verify real database counts displayed
        assert "Pending Event Approvals" in html
        assert "Approved / Active Events" in html
        assert "Campus Venues Available" in html
        assert "Inventory Resource Catalog" in html

        # Verify zero-state notices
        assert "Empty: Upload in Data Manager" in html
        assert "Clean Zero-State Active" in html
        assert "No pending approval requests." in html

        # Verify Admin Reset button and modal exist
        assert "Reset All Data" in html
        assert "resetDataModal" in html

@pytest.mark.anyio
async def test_organiser_dashboard_zero_counts_and_empty_state():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        # Login as organiser
        login_res = await client.post("/login", data={"email": "organiser@galgotias.edu", "password": "Organiser@123"})
        assert login_res.status_code == 302
        assert login_res.headers["location"] == "/organiser"

        res = await client.get("/organiser")
        assert res.status_code == 200
        html = res.text

        # Verify zero-state empty banner
        assert "No Campus Events Hosted Yet" in html
        assert "Plan Your First Event" in html

@pytest.mark.anyio
async def test_data_manager_dashboard_zero_counts_and_empty_state():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        # Login as data manager
        login_res = await client.post("/login", data={"email": "datamanager@galgotias.edu", "password": "Data@123"})
        assert login_res.status_code == 302
        assert login_res.headers["location"] == "/data-manager"

        res = await client.get("/data-manager")
        assert res.status_code == 200
        html = res.text

        # Verify zero state banner
        assert "Clean Starting State Active" in html
        assert "No venues yet" in html
        assert "No equipment yet" in html

@pytest.mark.anyio
async def test_admin_reset_access_control_and_execution():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        # 1. Non-admin (organiser) attempting to reset data MUST get 403 Forbidden
        await client.post("/login", data={"email": "organiser@galgotias.edu", "password": "Organiser@123"})
        res_forbidden = await client.post("/admin/reset-data")
        assert res_forbidden.status_code == 403

        # 2. Supervisor invokes reset data
        await client.get("/logout")
        await client.post("/login", data={"email": "admin@galgotias.edu", "password": "Admin@123"})
        
        # Test HTML form submission redirect
        res_reset_html = await client.post(
            "/admin/reset-data",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert res_reset_html.status_code == 302
        assert "/supervisor?reset_success=1" in res_reset_html.headers["location"]

        # 3. Test JSON API invocation
        res_reset_json = await client.post(
            "/admin/reset-data",
            headers={"Accept": "application/json"}
        )
        assert res_reset_json.status_code == 200
        data = res_reset_json.json()
        assert data["success"] is True

        # 4. Confirm audit log recorded
        audit = fetch_one("SELECT * FROM audit_log WHERE action = 'ADMIN_RESET_ALL_DATA' ORDER BY timestamp DESC LIMIT 1")
        assert audit is not None
        assert audit["actor"] == "admin@galgotias.edu"
        assert audit["result"] == "SUCCESS"
