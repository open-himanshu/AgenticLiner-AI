"""
Integration tests for AgenticLiner Autopilot Mode and End-to-End Autonomous Pipeline (Academic Operations).
"""
import pytest
from backend.core.planner.agent import AutopilotAgent
from backend.core.database.connection import get_connection

def test_autopilot_successful_execution():
    from backend.core.database.connection import execute_query
    execute_query(
        "INSERT OR IGNORE INTO rooms (id, name, capacity, location) VALUES ('room_auto_test', 'Main Campus Auditorium', 300, 'Block A')"
    )
    agent = AutopilotAgent()
    prompt = "Organize a campus coding hackathon for 150 students next Wednesday"
    
    # Use a unique test date to avoid collision with previously booked test runs
    test_date = "2026-12-15"
    result = agent.run_autopilot(
        prompt=prompt,
        date=test_date,
        start_time="09:00:00",
        end_time="17:00:00"
    )

    assert result["success"] is True
    assert result["venue"] is not None
    
    # Verify live timeline steps
    timeline = result["timeline"]
    assert len(timeline) >= 4
    tool_names = [step["tool"] for step in timeline]
    assert "adaptive_intake" in tool_names
    assert "find_free_venues" in tool_names
    assert "recommend_from_history" in tool_names
    assert "requisition_campus_resources" in tool_names

    # Check database persistence
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status FROM events WHERE id = ?", (result["event_id"],))
        assert cur.fetchone()["status"] == "allocated"

        # Check Outbox notification released
        cur.execute("SELECT status FROM outbox WHERE event_id = ?", (result["event_id"],))
        assert cur.fetchone()["status"] == "sent"

def test_autopilot_excessive_headcount():
    agent = AutopilotAgent()
    # 800 students exceeds campus largest hall (500 capacity)
    prompt = "Organize an all-university mega concert for 800 students"
    
    result = agent.run_autopilot(
        prompt=prompt,
        date="2026-11-25"
    )

    assert result["success"] is False
    assert "No campus venue satisfies" in result["error"]
