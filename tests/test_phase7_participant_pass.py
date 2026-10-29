"""
Pytest Suite for Student Participant Portal & Live Digital QR Gate Pass.
Covers registration, dynamic QR generation, mobile gate pass view,
gate check-in verification via QR scanning, and personalized session recommendations.
"""

import pytest
import httpx
from backend.api.main import app
from backend.services.admin_service import reset_all_operational_data
from backend.services.inventory_service import create_venue
from backend.services.event_workflow_service import create_event_request, approve_event_by_supervisor
from backend.services.pass_service import (
    get_or_create_student_profile,
    get_student_passes,
    generate_qr_base64,
    get_personalized_recommendations_for_student
)
from backend.modules.module2_scheduling.attendee_manager import AttendeeManager
from backend.core.database.connection import fetch_one

@pytest.fixture(autouse=True)
def setup_clean():
    reset_all_operational_data("admin@galgotias.edu")

@pytest.mark.anyio
async def test_qr_code_generation():
    uri = generate_qr_base64("https://agenticliner.campus.edu/verify/pass_123")
    assert uri.startswith("data:image/png;base64,")
    assert len(uri) > 100

@pytest.mark.anyio
async def test_student_profile_creation_and_retrieval():
    stud = get_or_create_student_profile(
        email="rohit@galgotias.edu",
        name="Rohit Sharma",
        department="B.Tech AI",
        year=3
    )
    assert stud["email"] == "rohit@galgotias.edu"
    assert stud["name"] == "Rohit Sharma"
    assert len(stud["interests_list"]) > 0

    # Retrieve again should return the existing record
    stud2 = get_or_create_student_profile("rohit@galgotias.edu")
    assert stud2["id"] == stud["id"]

@pytest.mark.anyio
async def test_student_passes_and_gate_qr_flow():
    # 1. Create and approve an event
    venue = await create_venue(name="Auditorium Hall D", capacity=150, location="Block D")
    ev = create_event_request(
        name="Campus Robotics Hackathon",
        brief="Robotics contest",
        event_type="hackathon",
        expected_participants=100,
        organizer_department="Robotics Club",
        organizer_email="organiser@galgotias.edu",
        room_id=venue["id"]
    )
    approve_event_by_supervisor(ev["event_id"])
    event_id = ev["event_id"]

    # 2. Register student
    attendee_mgr = AttendeeManager()
    reg = attendee_mgr.register_student(
        event_id=event_id,
        name="Pooja Sharma",
        email="pooja@galgotias.edu",
        department="Computer Science",
        year=2,
        interests=["Robotics", "Python"]
    )
    assert reg["success"] is True
    assert reg["status"] == "confirmed"
    reg_id = reg["registration_id"]

    # 3. Retrieve student passes
    passes = get_student_passes("pooja@galgotias.edu")
    assert len(passes) == 1
    p = passes[0]
    assert p["event_name"] == "Campus Robotics Hackathon"
    assert p["venue_name"] == "Auditorium Hall D"
    assert p["reg_status"] == "confirmed"
    assert p["qr_code_uri"].startswith("data:image/png;base64,")
    assert f"reg_id={reg_id}" in p["verify_url"]

    # 4. Gate Security Scanner scans the QR Pass via HTTP GET
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Browser / mobile camera scan returns HTML confirmation card
        scan_resp = await client.get(f"/api/pass/scan?reg_id={reg_id}", headers={"Accept": "text/html"})
        assert scan_resp.status_code == 200
        assert "ENTRY VERIFIED" in scan_resp.text
        assert "Pooja Sharma" in scan_resp.text
        assert "Campus Robotics Hackathon" in scan_resp.text

        # Verify attendance recorded in DB
        reg_db = fetch_one("SELECT status FROM registrations WHERE id = ?", (reg_id,))
        assert reg_db["status"] == "checked-in"

@pytest.mark.anyio
async def test_invalid_gate_pass_scan():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        scan_resp = await client.get("/api/pass/scan?reg_id=fake_pass_id", headers={"Accept": "text/html"})
        assert scan_resp.status_code == 404
        assert "Invalid Ticket" in scan_resp.text

@pytest.mark.anyio
async def test_personalized_recommendations():
    student = {
        "id": "stud_rec_01",
        "name": "Aman AI Student",
        "interests_list": ["Artificial Intelligence", "Python"]
    }
    recs = get_personalized_recommendations_for_student(student)
    assert len(recs["recommended_sessions"]) > 0
    # Top match should be AI related
    top_sess = recs["recommended_sessions"][0]
    assert "AI" in top_sess["title"] or "Python" in top_sess["title"]

@pytest.mark.anyio
async def test_http_participant_dashboard_and_registration_portal():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test public /register page loads with events
        reg_page = await client.get("/register")
        assert reg_page.status_code == 200
        assert "Campus Event Registration Portal" in reg_page.text

        # 2. Login as student
        login_res = await client.post("/login", data={"email": "student@galgotias.edu", "password": "Student@123"})
        assert login_res.status_code in (200, 302)

        # 3. Access /participant dashboard
        part_resp = await client.get("/participant")
        assert part_resp.status_code == 200
        assert "My Digital QR Gate Passes" in part_resp.text
        assert "Campus Event Assistant" in part_resp.text
