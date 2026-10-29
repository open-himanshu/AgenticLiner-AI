"""
Pytest Suite for Phase 5:
Supervisor & Organiser Event Workflow, Kavach Invariant Checks,
Dean Approval/Rejection Lifecycle, Waitlist Auto-Promotion, and Held Outbox Pattern.
"""

import pytest
import httpx
from backend.api.main import app
from backend.services.admin_service import reset_all_operational_data
from backend.services.inventory_service import create_venue, create_equipment
from backend.services.event_workflow_service import (
    create_event_request,
    approve_event_by_supervisor,
    reject_event_by_supervisor,
    get_event_with_details
)
from backend.core.safety.kavach import InvariantViolation
from backend.core.database.connection import fetch_one, fetch_all
from backend.modules.module2_scheduling.attendee_manager import AttendeeManager

@pytest.fixture(autouse=True)
def setup_clean_state():
    reset_all_operational_data("admin@galgotias.edu")

@pytest.mark.anyio
async def test_kavach_capacity_invariant_violation():
    # 1. Create a venue with 80 seats
    venue = await create_venue(
        name="Small Seminar Hall",
        capacity=80,
        location="Floor 1",
        has_projector=True,
        has_audio=True,
        requires_special_approval=False
    )

    # 2. Try to request an event with 150 students for this hall
    with pytest.raises(InvariantViolation) as exc_info:
        create_event_request(
            name="AI Overcrowded Workshop",
            brief="Hands on workshop",
            event_type="workshop",
            expected_participants=150,
            organizer_department="School of Computing",
            organizer_email="organiser@galgotias.edu",
            room_id=venue["id"]
        )

    assert "capacity_overrun" in str(exc_info.value)
    assert "exceeds room capacity of 80 seats" in str(exc_info.value)

@pytest.mark.anyio
async def test_kavach_room_overlap_invariant_violation():
    # 1. Create a venue
    venue = await create_venue(
        name="Auditorium B",
        capacity=250,
        location="Block B",
        has_projector=True,
        has_audio=True,
        requires_special_approval=False
    )

    # 2. Book event 1 from 10:00 to 13:00 (auto-approved since <=150 participants)
    ev1 = create_event_request(
        name="Morning Coding Fest",
        brief="Coding contest",
        event_type="hackathon",
        expected_participants=100,
        organizer_department="Coding Club",
        organizer_email="organiser@galgotias.edu",
        room_id=venue["id"],
        start_time="2026-11-20 10:00:00",
        end_time="2026-11-20 13:00:00"
    )
    assert ev1["success"] is True

    # 3. Try to book event 2 overlapping from 11:30 to 14:00
    with pytest.raises(InvariantViolation) as exc_info:
        create_event_request(
            name="Conflicting Robotics Workshop",
            brief="Robotics hands on",
            event_type="workshop",
            expected_participants=60,
            organizer_department="Robotics Club",
            organizer_email="organiser@galgotias.edu",
            room_id=venue["id"],
            start_time="2026-11-20 11:30:00",
            end_time="2026-11-20 14:00:00"
        )

    assert "room_overlap" in str(exc_info.value)
    assert "Auditorium B" in str(exc_info.value)

@pytest.mark.anyio
async def test_kavach_resource_stock_invariant_violation():
    # 1. Create a resource with stock 4
    res = await create_equipment(
        name="High-Res 4K Projector",
        category="equipment",
        stock=4,
        unit="unit",
        requires_approval=True
    )

    # 2. Try to requisition 10 units
    with pytest.raises(InvariantViolation) as exc_info:
        create_event_request(
            name="Movie Night",
            brief="Screening event",
            event_type="cultural",
            expected_participants=80,
            organizer_department="Cultural Society",
            organizer_email="organiser@galgotias.edu",
            requisitions=[{"resource_id": res["id"], "quantity": 10, "item_name": "High-Res 4K Projector"}]
        )

    assert "resource_exhaustion" in str(exc_info.value)
    assert "High-Res 4K Projector" in str(exc_info.value)

@pytest.mark.anyio
async def test_event_lifecycle_approval_and_outbox_release():
    # 1. Create venue and equipment
    venue = await create_venue(
        name="Main Convention Centre",
        capacity=500,
        location="Central Campus",
        requires_special_approval=True
    )
    eq = await create_equipment(
        name="JBL Wireless Sound Set",
        category="equipment",
        stock=10,
        unit="set"
    )

    # 2. Organiser submits event plan (requires Dean approval due to special venue)
    ev_req = create_event_request(
        name="Annual Technovation Summit 2026",
        brief="Flagship university technical conference and startup exhibition",
        event_type="conference",
        expected_participants=350,
        organizer_department="School of Computing & AI",
        organizer_email="organiser@galgotias.edu",
        room_id=venue["id"],
        start_time="2026-12-01 09:00:00",
        end_time="2026-12-01 18:00:00",
        requisitions=[{"resource_id": eq["id"], "quantity": 4, "item_name": eq["name"]}]
    )

    assert ev_req["success"] is True
    assert ev_req["approval_status"] == "pending_dean_approval"
    event_id = ev_req["event_id"]

    # Verify held outbox notice
    held_notices = fetch_all("SELECT * FROM outbox WHERE event_id = ? AND status = 'held'", (event_id,))
    assert len(held_notices) > 0

    # 3. Supervisor approves the event
    appr_res = approve_event_by_supervisor(
        event_id=event_id,
        supervisor_email="admin@galgotias.edu",
        remarks="Approved with full campus logistics support."
    )
    assert appr_res["success"] is True

    # 4. Check state transitions
    ev_updated = fetch_one("SELECT * FROM events WHERE id = ?", (event_id,))
    assert ev_updated["approval_status"] == "approved"
    assert ev_updated["status"] == "allocated"

    # Check bookings confirmed
    bookings = fetch_all("SELECT * FROM bookings WHERE event_id = ?", (event_id,))
    assert len(bookings) == 2  # room + equipment
    for b in bookings:
        assert b["status"] == "confirmed"
        assert b["approval_status"] == "approved"

    # Check equipment stock allocated
    eq_updated = fetch_one("SELECT * FROM resources WHERE id = ?", (eq["id"],))
    assert eq_updated["allocated_stock"] == 4

    # Check that HELD outbox notices were released to SENT
    unreleased = fetch_all("SELECT * FROM outbox WHERE event_id = ? AND status = 'held'", (event_id,))
    assert len(unreleased) == 0

    sent_notices = fetch_all("SELECT * FROM outbox WHERE event_id = ? AND status = 'sent'", (event_id,))
    assert len(sent_notices) >= 2  # Dean request released + approval congratulation

@pytest.mark.anyio
async def test_event_lifecycle_rejection():
    venue = await create_venue(name="Mini Hall", capacity=100, location="Ground Floor")
    ev_req = create_event_request(
        name="Campus Tech Talk",
        brief="Afternoon technical talk",
        event_type="seminar",
        expected_participants=80,
        organizer_department="Computing Club",
        organizer_email="organiser@galgotias.edu",
        room_id=venue["id"]
    )
    event_id = ev_req["event_id"]

    # Supervisor rejects
    rej_res = reject_event_by_supervisor(
        event_id=event_id,
        supervisor_email="admin@galgotias.edu",
        reason="Exceeds fire safety regulations and conflicts with academic exams."
    )
    assert rej_res["success"] is True

    ev = fetch_one("SELECT * FROM events WHERE id = ?", (event_id,))
    assert ev["approval_status"] == "rejected"
    assert ev["status"] == "cancelled"

    # Bookings marked cancelled
    bookings = fetch_all("SELECT * FROM bookings WHERE event_id = ?", (event_id,))
    for b in bookings:
        assert b["status"] == "cancelled"

@pytest.mark.anyio
async def test_attendee_waitlist_auto_promotion_and_checkin():
    # Create an event with room capacity of 2
    venue = await create_venue(name="Tiny Seminar Room", capacity=2, location="Block E")
    ev = create_event_request(
        name="VIP Closed Masterclass",
        brief="Exclusive 2-seat masterclass",
        event_type="workshop",
        expected_participants=2,
        organizer_department="AI Club",
        organizer_email="organiser@galgotias.edu",
        room_id=venue["id"]
    )
    # Approve to confirm booking
    approve_event_by_supervisor(ev["event_id"])
    event_id = ev["event_id"]

    attendee_mgr = AttendeeManager()

    # 1. Register student 1 -> CONFIRMED
    r1 = attendee_mgr.register_student(
        event_id=event_id,
        name="Alice Kumar",
        email="alice@galgotias.edu",
        department="Computer Science",
        year=3,
        interests=["AI"]
    )
    assert r1["status"] == "confirmed"

    # 2. Register student 2 -> CONFIRMED
    r2 = attendee_mgr.register_student(
        event_id=event_id,
        name="Bob Sharma",
        email="bob@galgotias.edu",
        department="Data Science",
        year=2,
        interests=["ML"]
    )
    assert r2["status"] == "confirmed"

    # 3. Register student 3 -> WAITLISTED (capacity of 2 reached!)
    r3 = attendee_mgr.register_student(
        event_id=event_id,
        name="Charlie Verma",
        email="charlie@galgotias.edu",
        department="AI",
        year=1,
        interests=["Robotics"]
    )
    assert r3["status"] == "waitlisted"

    # 4. Student 1 cancels -> Charlie MUST BE AUTO-PROMOTED to CONFIRMED!
    cancel_res = attendee_mgr.cancel_registration(r1["registration_id"])
    assert cancel_res["success"] is True
    assert cancel_res.get("waitlist_promotion_executed") is True
    assert cancel_res["promoted_student"]["email"] == "charlie@galgotias.edu"

    # Verify in DB
    charlie_reg = fetch_one("SELECT status FROM registrations WHERE id = ?", (r3["registration_id"],))
    assert charlie_reg["status"] == "confirmed"

    # 5. Gate Check-in for Bob
    checkin_res = attendee_mgr.check_in_attendee(r2["registration_id"])
    assert checkin_res["success"] is True
    bob_reg = fetch_one("SELECT status FROM registrations WHERE id = ?", (r2["registration_id"],))
    assert bob_reg["status"] == "checked-in"

@pytest.mark.anyio
async def test_http_api_event_plan_and_supervisor_actions():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        # Create venue
        v = await create_venue(name="Auditorium C", capacity=300, location="Block C")

        # 1. Login as Organiser
        await client.post("/login", data={"email": "organiser@galgotias.edu", "password": "Organiser@123"})

        # Submit Event Plan
        plan_resp = await client.post(
            "/api/events/plan",
            json={
                "name": "SparkX Innovation Fest",
                "brief": "Full day festival",
                "event_type": "hackathon",
                "expected_participants": 200,
                "room_id": v["id"],
                "organizer_department": "Innovation Club"
            }
        )
        assert plan_resp.status_code == 200
        plan_data = plan_resp.json()
        assert plan_data["success"] is True
        event_id = plan_data["event_id"]

        # 2. Login as Supervisor
        await client.get("/logout")
        await client.post("/login", data={"email": "admin@galgotias.edu", "password": "Admin@123"})

        # Supervisor approves
        appr_resp = await client.post(
            f"/api/events/{event_id}/approve",
            data={"remarks": "Looks great, approved."},
            headers={"Accept": "text/html"}
        )
        assert appr_resp.status_code == 302
        assert "/supervisor?approved=1" in appr_resp.headers["location"]

        # Verify event details endpoint
        details_resp = await client.get(f"/api/events/{event_id}")
        assert details_resp.status_code == 200
        details = details_resp.json()
        assert details["event"]["approval_status"] == "approved"
        assert len(details["bookings"]) > 0
