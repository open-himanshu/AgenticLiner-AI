"""
Phase 10: Tests for Autonomous Event Architect & Universal Command Agent.
Verifies prompt decomposition, automated venue & inventory requisition under Kavach,
Google OR-Tools CP-SAT conflict-free schedule generation, outbox notice staging,
and universal on-the-fly operational commands.
"""

import pytest
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.services.agentic_genesis_service import (
    parse_natural_language_event_prompt,
    execute_autonomous_event_genesis,
    execute_universal_command
)
from backend.core.database.connection import fetch_one

@pytest.fixture
def client():
    return TestClient(app)

def test_prompt_decomposition():
    # 1. AI Hackathon prompt
    p1 = "Organise a 2-day campus AI & Robotics Hackathon for 200 students with coding workshops, dinner catering, stage mics and 35k budget."
    res1 = parse_natural_language_event_prompt(p1)
    assert res1["headcount"] == 200
    assert res1["budget"] == 35000
    assert res1["event_type"] == "hackathon"
    assert "Robotics" in res1["domain"] or "AI" in res1["domain"]
    assert res1["needs_food"] is True
    assert res1["needs_sound"] is True

    # 2. Cultural dance prompt
    p2 = "Organise an annual dance & cultural fest for 150 students with sound system, stage lights and 20000 budget."
    res2 = parse_natural_language_event_prompt(p2)
    assert res2["headcount"] == 150
    assert res2["budget"] == 20000
    assert res2["event_type"] == "cultural"
    assert res2["needs_sound"] is True

def test_autonomous_event_genesis_execution():
    prompt = "Organize a campus Innovation Workshop for 120 students with lunch catering, microphones and 25k budget."
    res = execute_autonomous_event_genesis(prompt)
    assert res["success"] is True
    assert "event_id" in res
    assert res["headcount"] == 120
    assert "venue" in res
    assert res["venue"]["capacity"] >= 120
    assert len(res["execution_timeline"]) == 5
    assert len(res["allocated_items"]) > 0
    assert len(res["scheduled_sessions"]) == 4
    assert "outbox_notice_id" in res

    # Verify event stored in DB
    ev = fetch_one("SELECT * FROM events WHERE id = ?", (res["event_id"],))
    assert ev is not None
    assert "Workshop" in ev["name"]

    # Verify outbox notice staged as held
    notif = fetch_one("SELECT * FROM outbox WHERE id = ?", (res["outbox_notice_id"],))
    assert notif is not None
    assert notif["status"] == "held"

def test_universal_command_add_venue():
    cmd = "Add venue Sarabhai Space Lab with 220 seats in Block E Floor 2"
    res = execute_universal_command(cmd)
    assert res["success"] is True
    assert res["action"] == "VENUE_CREATED"
    assert "Sarabhai Space Lab" in res["message"]
    
    # Check in DB
    venue_in_db = fetch_one("SELECT * FROM rooms WHERE name LIKE '%Sarabhai%'")
    assert venue_in_db is not None
    assert venue_in_db["capacity"] == 220

def test_universal_command_add_equipment():
    cmd = "Add equipment UltraHD Wireless HDMI Transmitter with quantity 8 and price 1200"
    res = execute_universal_command(cmd)
    assert res["success"] is True
    assert res["action"] == "EQUIPMENT_CREATED"
    assert "UltraHD" in res["message"]

    # Check in DB
    eq_in_db = fetch_one("SELECT * FROM resources WHERE name LIKE '%UltraHD%'")
    assert eq_in_db is not None
    assert eq_in_db["stock"] >= 8

def test_universal_command_turnout_query():
    cmd = "Show turnout rate and registered count summary"
    res = execute_universal_command(cmd)
    assert res["success"] is True
    assert res["action"] == "ANALYTICS_QUERY"
    assert "Campus Status" in res["message"]
    assert "data" in res

def test_universal_command_certificate():
    cmd = "Generate certificate for Aryan Saxena"
    res = execute_universal_command(cmd)
    assert res["success"] is True
    assert res["action"] == "CERTIFICATE_GENERATED"
    assert "Aryan Saxena" in res["message"]
    assert "certificate_id" in res["data"]

def test_http_agent_genesis_and_command_endpoints(client):
    # 1. POST /api/agent/genesis
    res1 = client.post("/api/agent/genesis", json={
        "prompt": "Organize an Autonomous AI agents seminar for 100 students with sound system and 20k budget."
    })
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["success"] is True
    assert "event_id" in data1
    assert len(data1["execution_timeline"]) == 5

    # 2. POST /api/agent/universal-command
    res2 = client.post("/api/agent/universal-command", json={
        "command": "Show turnout rate and registered count summary"
    })
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["success"] is True
    assert data2["action"] == "ANALYTICS_QUERY"
