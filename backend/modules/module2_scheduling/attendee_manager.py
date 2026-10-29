"""
Module 2 & Platform: Attendee Management, Registration, and Waitlist Auto-Promotion.
Implements:
1. Student registration with automatic room capacity enforcement (Confirmed vs Waitlisted)
2. Automatic Waitlist Promotion upon cancellation
3. Live Session Check-in marking
4. CSV export generator.
"""

import io
import csv
import uuid
from typing import Dict, Any, List, Optional
from backend.core.database.connection import get_connection

class AttendeeManager:
    def __init__(self):
        pass

    def register_student(self, event_id: str, name: str, email: str, department: str, year: int, interests: List[str], preferred_sessions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Registers a student for an event.
        Enforces room capacity limit: if filled, queues into Waitlist.
        Stages corresponding notification in the Outbox.
        """
        preferred_sessions = preferred_sessions or []
        student_id = f"stud_{uuid.uuid4().hex[:6]}"
        reg_id = f"reg_{uuid.uuid4().hex[:8]}"

        with get_connection() as conn:
            cur = conn.cursor()

            # Ensure student record exists
            cur.execute("SELECT id FROM students WHERE email = ?", (email,))
            existing_stud = cur.fetchone()
            if existing_stud:
                student_id = existing_stud["id"]
            else:
                cur.execute(
                    "INSERT INTO students (id, name, email, department, year, interests) VALUES (?, ?, ?, ?, ?, ?)",
                    (student_id, name, email, department, year, str(interests))
                )

            # Check if student already registered for this event
            cur.execute("SELECT id, status FROM registrations WHERE event_id = ? AND student_id = ?", (event_id, student_id))
            existing_reg = cur.fetchone()
            if existing_reg:
                return {
                    "success": False,
                    "status": existing_reg["status"],
                    "message": f"Student is already registered for this event with status: {existing_reg['status']}."
                }

            # Determine Event Capacity from allocated room booking
            cur.execute("""
                SELECT r.capacity, e.expected_participants, e.name as event_name
                FROM events e
                LEFT JOIN bookings b ON b.event_id = e.id AND b.room_id IS NOT NULL AND b.status = 'confirmed'
                LEFT JOIN rooms r ON b.room_id = r.id
                WHERE e.id = ?
                LIMIT 1
            """, (event_id,))
            ev_row = cur.fetchone()
            max_capacity = 120
            event_name = "Campus Event"
            if ev_row:
                max_capacity = ev_row["capacity"] or ev_row["expected_participants"] or 120
                event_name = ev_row["event_name"] or event_name

            # Count current confirmed registrations
            cur.execute("SELECT count(*) as confirmed_count FROM registrations WHERE event_id = ? AND status = 'confirmed'", (event_id,))
            confirmed_count = cur.fetchone()["confirmed_count"]

            if confirmed_count < max_capacity:
                reg_status = "confirmed"
                msg_body = f"Congratulations {name}! Your registration for {event_name} is CONFIRMED. Please bring your student ID for gate QR check-in."
                msg_subject = f"Registration Confirmed: {event_name}"
            else:
                reg_status = "waitlisted"
                msg_body = f"Hello {name}, {event_name} has reached maximum hall capacity. You are placed on the PRIORITY WAITLIST. You will be automatically confirmed if a seat opens."
                msg_subject = f"Waitlisted: {event_name}"

            # Insert registration record
            cur.execute("""
                INSERT INTO registrations (id, event_id, student_id, status, interests_snapshot, preferred_sessions)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (reg_id, event_id, student_id, reg_status, str(interests), str(preferred_sessions)))

            # Stage notice in Outbox
            outbox_id = f"notif_{uuid.uuid4().hex[:8]}"
            cur.execute("""
                INSERT INTO outbox (id, event_id, recipient, subject, message, type, status)
                VALUES (?, ?, ?, ?, ?, 'confirmation', 'held')
            """, (outbox_id, event_id, email, msg_subject, msg_body))

            return {
                "success": True,
                "registration_id": reg_id,
                "student_id": student_id,
                "status": reg_status,
                "capacity_filled": confirmed_count + (1 if reg_status == "confirmed" else 0),
                "max_capacity": max_capacity,
                "message": f"Registration successful: Status is '{reg_status.upper()}'."
            }

    def cancel_registration(self, reg_id: str) -> Dict[str, Any]:
        """
        Cancels a registration and executes AUTOMATIC WAITLIST PROMOTION:
        The oldest waitlisted student is automatically promoted to 'confirmed',
        and an automated congratulations notification is staged to Outbox.
        """
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT r.id, r.event_id, r.status, s.name, s.email, e.name as event_name
                FROM registrations r
                JOIN students s ON r.student_id = s.id
                JOIN events e ON r.event_id = e.id
                WHERE r.id = ?
            """, (reg_id,))
            target = cur.fetchone()
            if not target:
                return {"success": False, "message": "Registration not found."}

            event_id = target["event_id"]
            old_status = target["status"]

            # Mark cancelled
            cur.execute("UPDATE registrations SET status = 'cancelled' WHERE id = ?", (reg_id,))

            promoted_student = None
            # If the cancelled person was 'confirmed', promote the first person from waitlist!
            if old_status == "confirmed":
                cur.execute("""
                    SELECT r.id, r.student_id, s.name, s.email
                    FROM registrations r
                    JOIN students s ON r.student_id = s.id
                    WHERE r.event_id = ? AND r.status = 'waitlisted'
                    ORDER BY r.registered_at ASC
                    LIMIT 1
                """, (event_id,))
                waitlisted_candidate = cur.fetchone()

                if waitlisted_candidate:
                    prom_reg_id = waitlisted_candidate["id"]
                    cur.execute("UPDATE registrations SET status = 'confirmed' WHERE id = ?", (prom_reg_id,))

                    # Stage auto-promotion congratulations email in Outbox
                    outbox_id = f"notif_prom_{uuid.uuid4().hex[:8]}"
                    subject = f"Good News! You have been promoted to Confirmed for {target['event_name']}"
                    message = (
                        f"Dear {waitlisted_candidate['name']},\n\n"
                        f"A seat has freed up for {target['event_name']}. The AgenticLiner Waitlist Engine has automatically promoted your status to CONFIRMED!\n\n"
                        "We look forward to seeing you at the event."
                    )
                    cur.execute("""
                        INSERT INTO outbox (id, event_id, recipient, subject, message, type, status)
                        VALUES (?, ?, ?, ?, ?, 'confirmation', 'held')
                    """, (outbox_id, event_id, waitlisted_candidate["email"], subject, message))

                    promoted_student = {
                        "registration_id": prom_reg_id,
                        "name": waitlisted_candidate["name"],
                        "email": waitlisted_candidate["email"]
                    }

            return {
                "success": True,
                "cancelled_registration_id": reg_id,
                "waitlist_promotion_executed": bool(promoted_student),
                "promoted_student": promoted_student,
                "message": "Registration cancelled successfully." + (f" Waitlisted student {promoted_student['name']} automatically promoted to Confirmed!" if promoted_student else "")
            }

    def check_in_attendee(self, reg_id: str, check_in_code: Optional[str] = "GATE-OPEN") -> Dict[str, Any]:
        """Marks attendee checked in for event sessions."""
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT r.student_id, r.event_id, r.status 
                FROM registrations r 
                WHERE r.id = ?
            """, (reg_id,))
            row = cur.fetchone()
            if not row:
                return {"success": False, "message": "Registration ID not found."}

            student_id = row["student_id"]
            event_id = row["event_id"]

            # Update registration status to checked-in
            cur.execute("UPDATE registrations SET status = 'checked-in' WHERE id = ?", (reg_id,))

            # Find primary keynote session to record attendance timestamp
            cur.execute("SELECT id FROM sessions WHERE event_id = ? LIMIT 1", (event_id,))
            sess = cur.fetchone()
            sess_id = sess["id"] if sess else "sess_default"

            att_id = f"att_{uuid.uuid4().hex[:8]}"
            cur.execute("""
                INSERT OR REPLACE INTO attendance (id, session_id, student_id, check_in_code)
                VALUES (?, ?, ?, ?)
            """, (att_id, sess_id, student_id, check_in_code))

            return {"success": True, "message": "Attendee checked in successfully."}

    def generate_attendees_csv(self, event_id: str) -> str:
        """Exports attendee list as a CSV string."""
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT r.id, s.name, s.email, s.department, s.year, r.status, r.registered_at
                FROM registrations r
                JOIN students s ON r.student_id = s.id
                WHERE r.event_id = ?
                ORDER BY r.registered_at ASC
            """, (event_id,))
            rows = cur.fetchall()

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Registration ID", "Student Name", "Email", "Department", "Academic Year", "Status", "Registered At"])
            for r in rows:
                writer.writerow([r["id"], r["name"], r["email"], r["department"], r["year"], r["status"], r["registered_at"]])

            return output.getvalue()
