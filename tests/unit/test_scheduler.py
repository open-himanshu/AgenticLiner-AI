"""
Unit tests for Google OR-Tools CP-SAT Event Scheduler.
"""
import pytest
from backend.core.scheduler.solver import EventScheduler

def test_conflict_free_scheduling():
    rooms = [
        {"id": "r1", "name": "Main Audi", "capacity": 300},
        {"id": "r2", "name": "Lab 1", "capacity": 50}
    ]
    slots = ["10:00 - 11:00", "11:30 - 12:30", "14:00 - 15:00"]
    sessions = [
        {"id": "s1", "title": "Opening Keynote", "expected_attendance": 250, "speaker_id": "spk1", "depends_on": None},
        {"id": "s2", "title": "Hands-on PyTorch", "expected_attendance": 40, "speaker_id": "spk2", "depends_on": "s1"},
        {"id": "s3", "title": "Closing Remarks", "expected_attendance": 200, "speaker_id": "spk1", "depends_on": "s2"}
    ]

    scheduler = EventScheduler(rooms, slots, sessions)
    result = scheduler.solve()

    assert result["success"] is True
    assert result["total_sessions_scheduled"] == 3

    sched_map = {item["session_id"]: item for item in result["schedule"]}
    
    # Check 1: Keynote s1 has 250 attendees, MUST be in Main Audi (capacity 300), NOT Lab 1 (capacity 50)
    assert sched_map["s1"]["room_id"] == "r1"
    
    # Check 2: Precedence: s1 (Keynote) happens strictly BEFORE s2 (Hands-on PyTorch)
    assert sched_map["s1"]["slot_index"] < sched_map["s2"]["slot_index"]
    
    # Check 3: Precedence: s2 happens strictly BEFORE s3
    assert sched_map["s2"]["slot_index"] < sched_map["s3"]["slot_index"]

    # Check 4: Speaker 1 (spk1) has s1 and s3; they must be at different slots
    assert sched_map["s1"]["slot_index"] != sched_map["s3"]["slot_index"]

def test_infeasible_scheduling():
    # Only 1 room with 50 capacity, but session needs 100
    rooms = [{"id": "r1", "name": "Small Room", "capacity": 50}]
    slots = ["10:00 - 11:00"]
    sessions = [{"id": "s1", "title": "Mega Gathering", "expected_attendance": 100, "speaker_id": "spk1", "depends_on": None}]

    scheduler = EventScheduler(rooms, slots, sessions)
    result = scheduler.solve()
    assert result["success"] is False
    assert result["status"] == "INFEASIBLE"
