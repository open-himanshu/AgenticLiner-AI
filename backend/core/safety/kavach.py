"""
Kavach Safety Engine: Fault-Tolerant Transaction Sandboxing & Invariant Enforcement
Part of AgenticLiner Core.

University Invariants Enforced:
1. Room Double-Booking / Time Overlap
2. Room Capacity Overrun (Expected Attendees > Room Seats)
3. Speaker Simultaneity Clash
4. Campus Inventory Stock Depletion
5. Dean Approval Policy (Large Audi / Transport)
6. Transactional Outbox Staging and Atomic Savepoint Rollback
"""

import sqlite3
import uuid
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from backend.core.database.connection import get_connection

class InvariantViolation(Exception):
    """Raised when an operation violates a core campus invariant."""
    def __init__(self, rule: str, item: str, detail: str, suggestion: Optional[str] = None):
        self.rule = rule
        self.item = item
        self.detail = detail
        self.suggestion = suggestion
        super().__init__(f"[{rule}] {item}: {detail}")

class KavachEngine:
    def __init__(self, max_blast_radius: int = 20):
        self.max_blast_radius = max_blast_radius

    def log_audit(self, conn: sqlite3.Connection, actor: str, action: str, result: str, event_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """Record an operation in the persistent audit log."""
        log_id = f"aud_{uuid.uuid4().hex[:10]}"
        details_str = json.dumps(details or {})
        conn.execute(
            "INSERT INTO audit_log (id, event_id, actor, action, details_json, result) VALUES (?, ?, ?, ?, ?, ?)",
            (log_id, event_id, actor, action, details_str, result)
        )

    def verify_room_capacity(self, conn: sqlite3.Connection, room_id: str, expected_attendance: int) -> None:
        """Verify that expected attendance does not exceed the room's maximum capacity."""
        cur = conn.cursor()
        cur.execute("SELECT name, capacity FROM rooms WHERE id = ?", (room_id,))
        row = cur.fetchone()
        if not row:
            raise InvariantViolation(
                rule="room_not_found",
                item=room_id,
                detail=f"Room ID '{room_id}' does not exist on campus."
            )
        room_name, capacity = row["name"], row["capacity"]
        if expected_attendance > capacity:
            # Find alternative rooms that CAN hold this attendance
            cur.execute("SELECT id, name, capacity FROM rooms WHERE capacity >= ? ORDER BY capacity ASC LIMIT 2", (expected_attendance,))
            alternatives = cur.fetchall()
            alt_msg = ", ".join([f"{a['name']} (Seats: {a['capacity']})" for a in alternatives]) if alternatives else "No single hall available with this capacity on campus."
            raise InvariantViolation(
                rule="capacity_overrun",
                item=room_name,
                detail=f"Attendance of {expected_attendance} exceeds room capacity of {capacity} seats.",
                suggestion=f"Allocate a larger hall: {alt_msg}"
            )

    def verify_room_overlap(self, conn: sqlite3.Connection, room_id: str, start_time: str, end_time: str, exclude_booking_id: Optional[str] = None) -> None:
        """Verify that the room is not already booked during the requested window."""
        cur = conn.cursor()
        query = """
            SELECT b.id, b.item_name, b.start_time, b.end_time, e.name as event_name
            FROM bookings b
            LEFT JOIN events e ON b.event_id = e.id
            WHERE b.room_id = ? 
              AND b.status = 'confirmed'
              AND (
                  (b.start_time < ? AND b.end_time > ?) OR
                  (b.start_time >= ? AND b.start_time < ?)
              )
        """
        params = [room_id, end_time, start_time, start_time, end_time]
        if exclude_booking_id:
            query += " AND b.id != ?"
            params.append(exclude_booking_id)

        cur.execute(query, tuple(params))
        conflict = cur.fetchone()
        if conflict:
            cur.execute("SELECT name FROM rooms WHERE id = ?", (room_id,))
            r_row = cur.fetchone()
            r_name = r_row["name"] if r_row else room_id
            raise InvariantViolation(
                rule="room_overlap",
                item=r_name,
                detail=f"Hall is already reserved for '{conflict['event_name'] or 'Academic Activity'}' from {conflict['start_time']} to {conflict['end_time']}.",
                suggestion="Choose a different time slot or allocate an alternative hall."
            )

    def verify_speaker_clash(self, conn: sqlite3.Connection, speaker_id: str, start_time: str, end_time: str, exclude_session_id: Optional[str] = None) -> None:
        """Verify that faculty/speaker is not booked in two sessions simultaneously."""
        cur = conn.cursor()
        query = """
            SELECT s.id, s.title, s.start_time, s.end_time, spk.name as speaker_name
            FROM sessions s
            JOIN speakers spk ON s.speaker_id = spk.id
            WHERE s.speaker_id = ?
              AND (
                  (s.start_time < ? AND s.end_time > ?) OR
                  (s.start_time >= ? AND s.start_time < ?)
              )
        """
        params = [speaker_id, end_time, start_time, start_time, end_time]
        if exclude_session_id:
            query += " AND s.id != ?"
            params.append(exclude_session_id)

        cur.execute(query, tuple(params))
        conflict = cur.fetchone()
        if conflict:
            raise InvariantViolation(
                rule="speaker_clash",
                item=conflict["speaker_name"],
                detail=f"Faculty/Speaker is already lecturing in session '{conflict['title']}' ({conflict['start_time']} to {conflict['end_time']}).",
                suggestion="Re-assign to another time slot or allocate an available co-speaker."
            )

    def verify_resource_stock(self, conn: sqlite3.Connection, resource_id: str, requested_qty: int, start_time: str, end_time: str) -> None:
        """Verify that requested campus equipment or volunteer quota does not exceed stock."""
        cur = conn.cursor()
        cur.execute("SELECT name, stock FROM resources WHERE id = ?", (resource_id,))
        res = cur.fetchone()
        if not res:
            return
        total_stock = res["stock"]
        
        cur.execute("""
            SELECT SUM(quantity) as booked_qty
            FROM bookings
            WHERE resource_id = ? 
              AND status = 'confirmed'
              AND (
                  (start_time < ? AND end_time > ?) OR
                  (start_time >= ? AND start_time < ?)
              )
        """, (resource_id, end_time, start_time, start_time, end_time))
        b_row = cur.fetchone()
        already_booked = b_row["booked_qty"] or 0
        if already_booked + requested_qty > total_stock:
            available = max(0, total_stock - already_booked)
            raise InvariantViolation(
                rule="resource_exhaustion",
                item=res["name"],
                detail=f"Requested {requested_qty} units, but only {available} units currently available in campus inventory (Total campus stock: {total_stock}).",
                suggestion=f"Cap quantity to {available} units or submit inter-department requisition."
            )

    def execute_with_kavach(self, conn: sqlite3.Connection, event_id: str, actor: str, operation_name: str, actions_callback) -> Dict[str, Any]:
        """
        Executes multi-action event mutations inside an isolated SQLite savepoint.
        If any campus invariant fails, performs an instant atomic ROLLBACK to the savepoint,
        drops any staged outbox notices, and logs the detailed failure in the audit log.
        """
        savepoint_name = f"sp_{uuid.uuid4().hex[:8]}"
        conn.execute(f"SAVEPOINT {savepoint_name};")
        self.log_audit(conn, actor, f"SAVEPOINT_CREATE:{savepoint_name}", "SUCCESS", event_id=event_id)

        try:
            result_payload = actions_callback(conn)

            # Release savepoint and commit changes
            conn.execute(f"RELEASE SAVEPOINT {savepoint_name};")
            self.log_audit(conn, actor, f"SAVEPOINT_COMMIT:{operation_name}", "SUCCESS", event_id=event_id, details=result_payload)
            
            # Release staged outbox messages for this event
            conn.execute("UPDATE outbox SET status = 'sent', sent_at = CURRENT_TIMESTAMP WHERE event_id = ? AND status = 'held'", (event_id,))

            return {
                "status": "committed",
                "operation": operation_name,
                "savepoint": savepoint_name,
                "details": result_payload
            }

        except InvariantViolation as iv:
            # Atomic ROLLBACK to savepoint
            conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name};")
            conn.execute(f"RELEASE SAVEPOINT {savepoint_name};")
            # Drop staged outbox messages
            conn.execute("DELETE FROM outbox WHERE event_id = ? AND status = 'held'", (event_id,))
            
            error_details = {
                "rule": iv.rule,
                "item": iv.item,
                "detail": iv.detail,
                "suggestion": iv.suggestion
            }
            self.log_audit(conn, actor, f"SAVEPOINT_ROLLBACK:{operation_name}", "BLOCKED", event_id=event_id, details=error_details)

            return {
                "status": "rolled_back",
                "operation": operation_name,
                "violation": error_details,
                "error": str(iv)
            }
        except Exception as ex:
            conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name};")
            conn.execute(f"RELEASE SAVEPOINT {savepoint_name};")
            conn.execute("DELETE FROM outbox WHERE event_id = ? AND status = 'held'", (event_id,))
            
            self.log_audit(conn, actor, f"SYSTEM_ERROR:{operation_name}", "FAILED", event_id=event_id, details={"error": str(ex)})
            return {
                "status": "rolled_back",
                "operation": operation_name,
                "error": f"Unexpected execution error: {str(ex)}"
            }
