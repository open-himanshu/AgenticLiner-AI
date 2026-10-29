"""
Pytest Suite for Phase 6:
Autonomous Agent DB Tools, Deterministic Tool Calling, and Kavach-Guarded Autopilot Pipeline.
"""

import pytest
import httpx
from backend.api.main import app
from backend.services.admin_service import reset_all_operational_data
from backend.services.inventory_service import create_venue, create_equipment
from backend.agent.tools import (
    tool_find_free_venues,
    tool_check_equipment,
    tool_recommend_from_history,
    tool_requisition_campus_resources
)
from backend.core.database.connection import fetch_one, fetch_all

@pytest.fixture(autouse=True)
def setup_clean():
    reset_all_operational_data("admin@galgotias.edu")

@pytest.mark.anyio
async def test_agent_tool_find_free_venues():
    # Create 2 venues
    v1 = await create_venue(name="Alpha Conference Hall", capacity=200, location="Ground Floor")
    v2 = await create_venue(name="Beta Meeting Room", capacity=50, location="1st Floor")

    # Search for min_capacity 100
    res = tool_find_free_venues(
        min_capacity=100,
        date="2026-12-05",
        start_time="10:00:00",
        end_time="13:00:00"
    )
    assert res["success"] is True
    assert res["available_venues_count"] == 1
    assert res["venues"][0]["name"] == "Alpha Conference Hall"

@pytest.mark.anyio
async def test_agent_tool_check_equipment():
    # Create equipment items
    await create_equipment(name="Wireless Mics Kit", category="equipment", stock=15)
    await create_equipment(name="Student Volunteer Crew", category="volunteers", stock=30)

    # Check equipment tool
    res = tool_check_equipment(category="equipment")
    assert res["count"] >= 1
    assert any(i["name"] == "Wireless Mics Kit" for i in res["items"])

@pytest.mark.anyio
async def test_agent_tool_recommend_from_history():
    res = tool_recommend_from_history(event_type="hackathon", headcount=150)
    assert res["event_type"] == "hackathon"
    assert res["headcount"] == 150
    assert len(res["recommendations"]) > 0
    assert any("power" in r["item_name"].lower() or "mic" in r["item_name"].lower() or "kit" in r["item_name"].lower() for r in res["recommendations"])

@pytest.mark.anyio
async def test_agent_tool_requisition_campus_resources_success():
    venue = await create_venue(name="Gamma Audi", capacity=300, location="Block G")
    eq = await create_equipment(name="Extension Boards", category="equipment", stock=20)

    # First insert event record to satisfy foreign key
    from backend.core.database.connection import execute_query
    execute_query(
        "INSERT INTO events (id, name, brief, event_type, expected_participants) VALUES (?, ?, ?, ?, ?)",
        ("ev_test_agent_01", "Gamma Hackathon", "Brief description", "hackathon", 180)
    )

    # Requisition via tool inside Kavach savepoint
    res = tool_requisition_campus_resources(
        event_id="ev_test_agent_01",
        room_id=venue["id"],
        attendance=180,
        items_json=[{"resource_id": eq["id"], "quantity": 5}],
        date="2026-12-10",
        start_time="09:00:00",
        end_time="14:00:00"
    )

    assert res["status"] == "committed"
    details = res["details"]
    assert details["room_name"] == "Gamma Audi"

    # Check DB allocations
    bookings = fetch_all("SELECT * FROM bookings WHERE event_id = 'ev_test_agent_01'")
    assert len(bookings) == 2  # room + equipment

    eq_db = fetch_one("SELECT allocated_stock FROM resources WHERE id = ?", (eq["id"],))
    assert eq_db["allocated_stock"] == 5

@pytest.mark.anyio
async def test_agent_tool_requisition_kavach_rollback_on_violation():
    venue = await create_venue(name="Tiny Classroom", capacity=40, location="Block T")

    # Attendance 120 exceeds capacity 40 -> Kavach MUST catch and rollback
    res = tool_requisition_campus_resources(
        event_id="ev_test_agent_fail",
        room_id=venue["id"],
        attendance=120,
        items_json=[],
        date="2026-12-10",
        start_time="09:00:00",
        end_time="14:00:00"
    )

    assert res["status"] == "rolled_back"
    assert res["violation"]["rule"] == "capacity_overrun"

    # Verify nothing was committed in bookings
    bookings = fetch_all("SELECT * FROM bookings WHERE event_id = 'ev_test_agent_fail'")
    assert len(bookings) == 0

@pytest.mark.anyio
async def test_http_agent_run_endpoint():
    # Create venue for autonomous planner to find
    await create_venue(name="Main Campus Convention Hall", capacity=300, location="Admin Block")
    await create_equipment(name="Extension Boards (Spike Strips)", category="equipment", stock=50)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Call POST /agent/run
        resp = await client.post(
            "/agent/run",
            json={
                "prompt": "Organize a campus coding hackathon for 180 students",
                "date": "2026-12-20",
                "start_time": "09:00:00",
                "end_time": "17:00:00"
            }
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["timeline"]) >= 4
        assert "Main Campus Convention Hall" in data["venue"]
