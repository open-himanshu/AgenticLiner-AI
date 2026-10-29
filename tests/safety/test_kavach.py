"""
Unit tests for Kavach Safety Engine (Academic Edition: Invariant checking, Savepoint and Rollback, Outbox staging).
"""
import pytest
import sqlite3
import uuid
from backend.core.database.connection import get_connection
from backend.core.database.init_db import init_database, seed_campus_data
from backend.core.safety.kavach import KavachEngine, InvariantViolation

@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    init_database(conn)
    seed_campus_data(conn)
    yield conn
    conn.close()

def test_kavach_successful_commit(test_db):
    kavach = KavachEngine()
    event_id = f"ev_test_{uuid.uuid4().hex[:6]}"
    
    test_db.execute(
        "INSERT INTO events (id, name, brief, expected_participants) VALUES (?, ?, ?, ?)",
        (event_id, "Test Hackathon", "A 2-day hackathon", 50)
    )

    def valid_booking_action(conn):
        kavach.verify_room_capacity(conn, "room_sem_101", 50)
        kavach.verify_room_overlap(conn, "room_sem_101", "2026-11-20 10:00:00", "2026-11-20 12:00:00")
        
        b_id = f"bk_{uuid.uuid4().hex[:6]}"
        conn.execute(
            "INSERT INTO bookings (id, event_id, room_id, item_name, category, start_time, end_time, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (b_id, event_id, "room_sem_101", "Seminar Hall 1", "venue", "2026-11-20 10:00:00", "2026-11-20 12:00:00", "confirmed")
        )
        m_id = f"msg_{uuid.uuid4().hex[:6]}"
        conn.execute(
            "INSERT INTO outbox (id, event_id, recipient, subject, message, status) VALUES (?, ?, ?, ?, ?, 'held')",
            (m_id, event_id, "student@galgotias.edu", "Booking Confirmed", "Your hall is booked.")
        )
        return {"booking_id": b_id}

    result = kavach.execute_with_kavach(test_db, event_id, "test_user", "book_venue", valid_booking_action)
    
    assert result["status"] == "committed"
    cur = test_db.cursor()
    cur.execute("SELECT count(*) FROM bookings WHERE event_id = ?", (event_id,))
    assert cur.fetchone()[0] == 1

    cur.execute("SELECT status FROM outbox WHERE event_id = ?", (event_id,))
    assert cur.fetchone()[0] == "sent"

def test_kavach_capacity_overrun_rollback(test_db):
    kavach = KavachEngine()
    event_id = f"ev_overrun_{uuid.uuid4().hex[:6]}"
    
    test_db.execute(
        "INSERT INTO events (id, name, brief, expected_participants) VALUES (?, ?, ?, ?)",
        (event_id, "Mega Workshop", "Massive AI workshop", 150)
    )

    def invalid_capacity_action(conn):
        kavach.verify_room_capacity(conn, "room_comp_lab", 150)
        
        conn.execute(
            "INSERT INTO bookings (id, event_id, room_id, item_name, category, start_time, end_time, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("bk_bad", event_id, "room_comp_lab", "Computing Lab 4", "venue", "2026-11-20 10:00:00", "2026-11-20 12:00:00", "confirmed")
        )
        conn.execute(
            "INSERT INTO outbox (id, event_id, recipient, subject, message, status) VALUES (?, ?, ?, ?, ?, 'held')",
            ("msg_bad", event_id, "student@galgotias.edu", "Bad Notice", "Wrong room booked")
        )
        return {"status": "ok"}

    result = kavach.execute_with_kavach(test_db, event_id, "test_user", "book_oversized", invalid_capacity_action)

    assert result["status"] == "rolled_back"
    assert result["violation"]["rule"] == "capacity_overrun"
    assert "Allocate a larger hall:" in result["violation"]["suggestion"]

    cur = test_db.cursor()
    cur.execute("SELECT count(*) FROM bookings WHERE event_id = ?", (event_id,))
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT count(*) FROM outbox WHERE event_id = ?", (event_id,))
    assert cur.fetchone()[0] == 0
