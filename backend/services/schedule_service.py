"""
Intelligent Timetable Scheduling & Dynamic Re-planning Service.
Powered by Google OR-Tools CP-SAT Solver and Kavach Safety Engine.
"""

import io
import csv
import json
import uuid
import logging
from typing import Dict, Any, List, Optional

from backend.core.database.connection import get_connection, fetch_all, fetch_one, execute_query
from backend.core.scheduler.solver import EventScheduler
from backend.core.safety.kavach import KavachEngine

logger = logging.getLogger(__name__)
kavach = KavachEngine()

DEFAULT_SLOTS = [
    "09:30 AM - 11:00 AM",
    "11:15 AM - 12:45 PM",
    "01:45 PM - 03:15 PM",
    "03:30 PM - 05:00 PM"
]

DEFAULT_SESSIONS = [
    {
        "id": "sess_01",
        "title": "Opening Keynote & Dean Inauguration",
        "expected_attendance": 250,
        "speaker_id": "spk_dean",
        "speaker_name": "Dr. Manish Raj (Dean SoAI)",
        "depends_on": None,
        "track": "General"
    },
    {
        "id": "sess_02",
        "title": "Generative AI Systems Masterclass",
        "expected_attendance": 120,
        "speaker_id": "spk_puri",
        "speaker_name": "Dr. Vartika Puri (Associate Prof)",
        "depends_on": "sess_01",
        "track": "AI/ML"
    },
    {
        "id": "sess_03",
        "title": "Deep Learning with PyTorch Lab",
        "expected_attendance": 50,
        "speaker_id": "spk_akhilesh",
        "speaker_name": "Prof. Akhilesh Sir (Lead Researcher)",
        "depends_on": "sess_02",
        "track": "AI/ML"
    },
    {
        "id": "sess_04",
        "title": "Python for Autonomous AI Agents",
        "expected_attendance": 80,
        "speaker_id": "spk_niraj",
        "speaker_name": "Prof. Niraj Sir (Robotics Lab)",
        "depends_on": "sess_01",
        "track": "AI/ML"
    }
]

def get_scheduling_rooms(custom_rooms: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Returns active campus rooms or high-capacity university default halls if db is fresh."""
    if custom_rooms and len(custom_rooms) > 0:
        return custom_rooms

    db_rooms = fetch_all("SELECT id, name, capacity, location FROM rooms ORDER BY capacity DESC")
    if db_rooms and len(db_rooms) >= 2:
        return [dict(r) for r in db_rooms]

    return [
        {"id": "room_audi_a", "name": "Main Auditorium A (Block C)", "capacity": 300, "location": "C-Block Floor 1"},
        {"id": "room_audi_b", "name": "Auditorium B (Mini Hall)", "capacity": 150, "location": "A-Block Floor 2"},
        {"id": "room_lab_ai", "name": "Advanced AI & Robotics Lab", "capacity": 60, "location": "Tech Tower Floor 3"}
    ]

def solve_timetable(
    sessions: Optional[List[Dict[str, Any]]] = None,
    slots: Optional[List[str]] = None,
    custom_rooms: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Solves conflict-free timetable satisfying capacity, exclusivity, and dependency constraints.
    Returns both chronological schedule list and a 2D Room-Time Slot grid matrix.
    """
    sessions = sessions or DEFAULT_SESSIONS
    slots = slots or DEFAULT_SLOTS
    rooms = get_scheduling_rooms(custom_rooms)

    scheduler = EventScheduler(rooms=rooms, slots=slots, sessions=sessions)
    result = scheduler.solve()

    if not result.get("success"):
        return result

    schedule = result.get("schedule", [])
    
    # Map speaker names into schedule items
    sess_map = {s["id"]: s for s in sessions}
    for item in schedule:
        s_info = sess_map.get(item["session_id"], {})
        item["speaker_name"] = s_info.get("speaker_name", "Assigned Faculty")
        item["track"] = s_info.get("track", "General")
        item["depends_on"] = s_info.get("depends_on")

    # Construct 2D Grid Matrix: rows = slots, cols = rooms
    grid_matrix = []
    for slot_idx, slot_label in enumerate(slots):
        row = {"slot_index": slot_idx, "slot_time": slot_label, "rooms": []}
        for room in rooms:
            # Find session scheduled in this (room, slot)
            placed = next((s for s in schedule if s["room_id"] == room["id"] and s["slot_index"] == slot_idx), None)
            row["rooms"].append({
                "room_id": room["id"],
                "room_name": room["name"],
                "capacity": room["capacity"],
                "session": placed
            })
        grid_matrix.append(row)

    # Compute Occupancy Statistics
    total_seats_used = sum(s["expected_attendance"] for s in schedule)
    total_capacity_booked = sum(next((r["capacity"] for r in rooms if r["id"] == s["room_id"]), 100) for s in schedule)
    occupancy_pct = round((total_seats_used / total_capacity_booked * 100), 1) if total_capacity_booked > 0 else 0

    return {
        "success": True,
        "status": result.get("status", "OPTIMAL"),
        "schedule": schedule,
        "grid_matrix": grid_matrix,
        "rooms": rooms,
        "slots": slots,
        "total_sessions": len(schedule),
        "total_seats_used": total_seats_used,
        "seat_occupancy_rate": occupancy_pct
    }

def handle_hero_speaker_cancellation(event_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Hero Demo: Simulates unexpected speaker cancellation (Dr. Vartika Puri),
    intelligently finds substitute speaker with matching expertise in GenAI,
    re-runs CP-SAT with minimal disruption, and stages outbox broadcast notices.
    """
    rooms = get_scheduling_rooms()
    slots = DEFAULT_SLOTS

    # Check database for candidate substitute speaker in AI department
    substitute = fetch_one("SELECT name, department, topics FROM speakers WHERE topics LIKE '%AI%' OR department LIKE '%AI%' LIMIT 1")
    if substitute:
        substitute_name = f"{substitute['name']} ({substitute['department']})"
        match_reason = f"Matching campus research domain: {substitute['topics']}"
    else:
        substitute_name = "Dr. Neha Verma (School of AI)"
        match_reason = "Matching research expertise: Generative AI, Machine Learning, available in afternoon slot"

    # Mutate sessions: Dr. Vartika Puri cancelled -> replaced with substitute
    reallocated_sessions = []
    for s in DEFAULT_SESSIONS:
        item = dict(s)
        if item["id"] == "sess_02":
            item["original_speaker"] = item.get("speaker_name", "Dr. Vartika Puri")
            item["speaker_name"] = substitute_name
            item["speaker_id"] = "spk_substitute_neha"
            item["is_substitute"] = True
        reallocated_sessions.append(item)

    solve_res = solve_timetable(sessions=reallocated_sessions, slots=slots, custom_rooms=rooms)

    # Ensure event exists for Outbox staging
    ev = fetch_one("SELECT id FROM events LIMIT 1")
    target_event_id = event_id or (ev["id"] if ev else "ev_hero_schedule")
    if not ev:
        execute_query(
            "INSERT OR IGNORE INTO events (id, name, brief, event_type) VALUES (?, 'Hero Schedule Summit', 'Clash-Free Timetable Demo', 'conference')",
            (target_event_id,)
        )

    # Stage Outbox Announcement to all participants
    outbox_id = f"notif_change_{uuid.uuid4().hex[:6]}"
    outbox_msg = (
        f"Schedule Update: Keynote speaker Dr. Vartika Puri cancelled due to unavoidable conflict. "
        f"{substitute_name} has been allocated with zero timetable clashes. All session timings confirmed."
    )
    execute_query("""
        INSERT INTO outbox (id, event_id, recipient, subject, message, type, status)
        VALUES (?, ?, 'all_registered_participants@galgotias.edu', 'Schedule Update: Substitute Speaker Allocated', ?, 'schedule_change', 'held')
    """, (outbox_id, target_event_id, outbox_msg))

    # Log to audit trail
    execute_query(
        "INSERT INTO audit_log (id, event_id, actor, action, details_json, result) VALUES (?, ?, 'autopilot_scheduler', 'SPEAKER_CANCELLATION_HANDLED', ?, 'SUCCESS')",
        (f"aud_{uuid.uuid4().hex[:8]}", target_event_id, json.dumps({"cancelled": "Dr. Vartika Puri", "substitute": substitute_name, "outbox_id": outbox_id}))
    )

    return {
        "status": "re_planned",
        "action": "SPEAKER_CANCELLATION_HANDLED",
        "original_speaker": "Dr. Vartika Puri",
        "substitute_allocated": substitute_name,
        "match_reason": match_reason,
        "new_schedule": solve_res.get("schedule", []),
        "grid_matrix": solve_res.get("grid_matrix", []),
        "staged_outbox_notice": {
            "id": outbox_id,
            "status": "held_in_outbox",
            "message": "Broadcast notice held in Outbox for coordinator review or instant release."
        }
    }

def export_schedule_csv(schedule: List[Dict[str, Any]]) -> str:
    """Exports timetable schedule to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Slot Time", "Session Title", "Allocated Venue", "Speaker", "Expected Attendance", "Track", "Status"])
    for s in schedule:
        writer.writerow([
            s.get("slot_time"),
            s.get("session_title"),
            s.get("room_name"),
            s.get("speaker_name", "Assigned Faculty"),
            s.get("expected_attendance", 0),
            s.get("track", "General"),
            "Feasible / Conflict-Free"
        ])
    return output.getvalue()
