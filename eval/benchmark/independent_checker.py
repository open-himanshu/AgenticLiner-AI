"""
Independent Database Checker Script for AgenticLiner (Section 11 of Master Plan).
Audits the raw SQLite database directly WITHOUT relying on Kavach's own assertions.
Verifies:
1. Double-booking / time overlapping violations.
2. Capacity violations (attendance > room capacity).
3. Speaker collision violations.
4. Outbox leakage (unreleased notifications on failed transactions).
"""

import sqlite3
from typing import Dict, Any, List
from backend.core.database.connection import get_connection

class IndependentDBChecker:
    def __init__(self):
        pass

    def run_full_audit(self) -> Dict[str, Any]:
        with get_connection() as conn:
            cur = conn.cursor()

            # 1. Check for Room Overlaps / Double Bookings
            cur.execute("""
                SELECT b1.id as booking_1, b2.id as booking_2, b1.room_id, r.name as room_name,
                       b1.start_time, b1.end_time
                FROM bookings b1
                JOIN bookings b2 ON b1.room_id = b2.room_id 
                                AND b1.id < b2.id
                                AND b1.status = 'confirmed' 
                                AND b2.status = 'confirmed'
                JOIN rooms r ON b1.room_id = r.id
                WHERE (
                    (b1.start_time < b2.end_time AND b1.end_time > b2.start_time)
                )
            """)
            overlaps = cur.fetchall()

            # 2. Check for Room Capacity Violations
            cur.execute("""
                SELECT s.id as session_id, s.title, s.expected_attendance, r.name as room_name, r.capacity
                FROM sessions s
                JOIN rooms r ON s.room_id = r.id
                WHERE s.expected_attendance > r.capacity
            """)
            capacity_violations = cur.fetchall()

            # 3. Check for Speaker Double-booking Violations
            cur.execute("""
                SELECT s1.id as session_1, s2.id as session_2, spk.name as speaker_name,
                       s1.start_time, s1.end_time
                FROM sessions s1
                JOIN sessions s2 ON s1.speaker_id = s2.speaker_id 
                                AND s1.id < s2.id
                JOIN speakers spk ON s1.speaker_id = spk.id
                WHERE (
                    (s1.start_time < s2.end_time AND s1.end_time > s2.start_time)
                )
            """)
            speaker_clashes = cur.fetchall()

            # 4. Check for Outbox Leakage
            cur.execute("""
                SELECT o.id, o.recipient, o.subject, o.status, e.status as event_status
                FROM outbox o
                JOIN events e ON o.event_id = e.id
                WHERE o.status = 'sent' AND e.status IN ('cancelled', 'draft', 'rolled_back')
            """)
            outbox_leaks = cur.fetchall()

            total_bookings = cur.execute("SELECT count(*) FROM bookings WHERE status = 'confirmed'").fetchone()[0]
            total_events = cur.execute("SELECT count(*) FROM events").fetchone()[0]
            total_audits = cur.execute("SELECT count(*) FROM audit_log").fetchone()[0]

            is_pure = (len(overlaps) == 0 and len(capacity_violations) == 0 and len(speaker_clashes) == 0 and len(outbox_leaks) == 0)

            return {
                "audit_passed": is_pure,
                "total_events_in_db": total_events,
                "confirmed_bookings_in_db": total_bookings,
                "audit_log_entries": total_audits,
                "violations": {
                    "room_overlaps_count": len(overlaps),
                    "capacity_overruns_count": len(capacity_violations),
                    "speaker_clashes_count": len(speaker_clashes),
                    "outbox_leaks_count": len(outbox_leaks)
                },
                "details": {
                    "overlaps": [dict(r) for r in overlaps],
                    "capacity_violations": [dict(r) for r in capacity_violations],
                    "speaker_clashes": [dict(r) for r in speaker_clashes]
                }
            }

if __name__ == "__main__":
    checker = IndependentDBChecker()
    res = checker.run_full_audit()
    print("Independent DB Audit Results:")
    print(f"Overall State Pure: {res['audit_passed']}")
    print(f"Confirmed Bookings: {res['confirmed_bookings_in_db']}")
    print(f"Violations Detected: {res['violations']}")
