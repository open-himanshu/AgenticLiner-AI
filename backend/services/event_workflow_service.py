"""
Event Lifecycle & Safety Workflow Service.
Manages event requests, Dean/Supervisor approval workflow, Kavach invariant checks,
resource allocations, and transactional Outbox release.
"""

import uuid
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.core.database.connection import get_connection, fetch_one, fetch_all, execute_query
from backend.core.safety.kavach import KavachEngine, InvariantViolation

logger = logging.getLogger(__name__)
kavach = KavachEngine()

def create_event_request(
    name: str,
    brief: str,
    event_type: str,
    expected_participants: int,
    organizer_department: str,
    organizer_email: str,
    room_id: Optional[str] = None,
    start_time: str = "2026-11-15 10:00:00",
    end_time: str = "2026-11-15 13:00:00",
    requisitions: Optional[List[Dict[str, Any]]] = None,
    image_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Submits an event plan. Enforces Kavach invariants (room capacity, room overlap, equipment stock).
    Determines if Dean approval is mandatory (special venue, requested stock with Dean policy, or large headcount).
    Stages event, initial bookings, and held notices in outbox.
    """
    requisitions = requisitions or []
    event_id = f"ev_{uuid.uuid4().hex[:8]}"

    with get_connection() as conn:
        # Invariant 1 & 2: Room Capacity & Overlap
        requires_dean = False
        room_name = "Campus Ground"

        if room_id:
            cur = conn.cursor()
            cur.execute("SELECT name, capacity, requires_special_approval FROM rooms WHERE id = ?", (room_id,))
            room = cur.fetchone()
            if not room:
                raise InvariantViolation("room_not_found", room_id, f"Room {room_id} not found on campus.")

            room_name = room["name"]
            if room["requires_special_approval"]:
                requires_dean = True

            # Enforce room capacity
            kavach.verify_room_capacity(conn, room_id, expected_participants)
            # Enforce schedule overlap
            kavach.verify_room_overlap(conn, room_id, start_time, end_time)

        # Invariant 3: Equipment Stock Check
        for req in requisitions:
            res_id = req.get("resource_id") or req.get("id")
            qty = int(req.get("quantity") or req.get("qty") or 1)
            if res_id:
                cur = conn.cursor()
                cur.execute("SELECT name, requires_approval FROM resources WHERE id = ?", (res_id,))
                res_row = cur.fetchone()
                if res_row and res_row["requires_approval"]:
                    requires_dean = True
                kavach.verify_resource_stock(conn, res_id, qty, start_time, end_time)

        # Large events automatically require Dean sign-off
        if expected_participants > 150:
            requires_dean = True

        approval_status = "pending_dean_approval" if requires_dean else "auto_approved"
        event_status = "planned" if requires_dean else "allocated"

        # Insert Event Record
        conn.execute(
            """INSERT INTO events (id, name, brief, event_type, expected_participants, organizer_department, approval_status, status, image_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_id, name.strip(), brief.strip(), event_type.lower(), expected_participants, organizer_department.strip(), approval_status, event_status, image_url)
        )

        # Book Venue
        if room_id:
            booking_id = f"bk_room_{uuid.uuid4().hex[:6]}"
            conn.execute(
                """INSERT INTO bookings (id, event_id, room_id, item_name, category, start_time, end_time, quantity, approval_status, status)
                   VALUES (?, ?, ?, ?, 'venue', ?, ?, 1, ?, ?)""",
                (booking_id, event_id, room_id, room_name, start_time, end_time, approval_status, "confirmed" if not requires_dean else "pending")
            )

        # Book Equipment Requisitions
        for req in requisitions:
            res_id = req.get("resource_id") or req.get("id")
            item_name = req.get("name") or req.get("item_name") or "Equipment"
            cat = req.get("category") or "equipment"
            qty = int(req.get("quantity") or req.get("qty") or 1)
            bk_id = f"bk_res_{uuid.uuid4().hex[:6]}"

            conn.execute(
                """INSERT INTO bookings (id, event_id, resource_id, item_name, category, start_time, end_time, quantity, approval_status, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (bk_id, event_id, res_id, item_name, cat, start_time, end_time, qty, approval_status, "confirmed" if not requires_dean else "pending")
            )

            # If auto-approved, allocate immediately
            if not requires_dean and res_id:
                conn.execute(
                    "UPDATE resources SET allocated_stock = allocated_stock + ? WHERE id = ?",
                    (qty, res_id)
                )

        # Outbox Notice Staging (Transactional Outbox Pattern)
        outbox_id = f"notif_{uuid.uuid4().hex[:8]}"
        if requires_dean:
            subject = f"Dean Approval Request: {name} ({organizer_department})"
            message = (
                f"An event request requiring Dean approval has been submitted:\n"
                f"Event: {name}\n"
                f"Organized by: {organizer_department} ({organizer_email})\n"
                f"Venue: {room_name}\n"
                f"Expected Headcount: {expected_participants}\n"
                f"Requisitions: {len(requisitions)} items."
            )
            # Notice for Dean is held until reviewed
            conn.execute(
                """INSERT INTO outbox (id, event_id, recipient, subject, message, type, status)
                   VALUES (?, ?, 'admin@galgotias.edu', ?, ?, 'dean_approval_request', 'held')""",
                (outbox_id, event_id, subject, message)
            )
        else:
            subject = f"Event Confirmed: {name}"
            message = f"Your event '{name}' has been auto-approved and allocated campus resources."
            conn.execute(
                """INSERT INTO outbox (id, event_id, recipient, subject, message, type, status, sent_at)
                   VALUES (?, ?, ?, ?, ?, 'confirmation', 'sent', CURRENT_TIMESTAMP)""",
                (outbox_id, event_id, organizer_email, subject, message)
            )

        # Audit Log
        kavach.log_audit(
            conn,
            actor=organizer_email,
            action="CREATE_EVENT_REQUEST",
            result="SUCCESS",
            event_id=event_id,
            details={"name": name, "approval_status": approval_status, "requires_dean": requires_dean}
        )

        return {
            "success": True,
            "event_id": event_id,
            "name": name,
            "approval_status": approval_status,
            "status": event_status,
            "requires_dean_approval": requires_dean
        }

def approve_event_by_supervisor(event_id: str, supervisor_email: str = "admin@galgotias.edu", remarks: str = "") -> Dict[str, Any]:
    """
    Supervisor (Dean Office) approval action.
    Updates event status to 'approved', confirms all staged bookings,
    increments allocated_stock for resources, releases held outbox notices,
    and logs immutable audit trail.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        event = cur.fetchone()
        if not event:
            raise ValueError(f"Event {event_id} not found.")

        # Update Event status
        conn.execute(
            """UPDATE events 
               SET approval_status = 'approved', status = 'allocated', updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (event_id,)
        )

        # Confirm all bookings for this event
        conn.execute(
            """UPDATE bookings 
               SET status = 'confirmed', approval_status = 'approved'
               WHERE event_id = ?""",
            (event_id,)
        )

        # Allocate stock for resources
        cur.execute("SELECT resource_id, quantity FROM bookings WHERE event_id = ? AND resource_id IS NOT NULL", (event_id,))
        allocations = cur.fetchall()
        for alloc in allocations:
            conn.execute(
                "UPDATE resources SET allocated_stock = allocated_stock + ? WHERE id = ?",
                (alloc["quantity"], alloc["resource_id"])
            )

        # Release HELD Outbox Notices (Atomic Outbox Pattern)
        conn.execute(
            """UPDATE outbox 
               SET status = 'sent', sent_at = CURRENT_TIMESTAMP 
               WHERE event_id = ? AND status = 'held'""",
            (event_id,)
        )

        # Create Official Approval Notification for Organiser
        notif_id = f"notif_appr_{uuid.uuid4().hex[:8]}"
        appr_subject = f"Official Dean Approval: {event['name']}"
        appr_body = (
            f"Dear Organiser,\n\n"
            f"Your event '{event['name']}' has been officially APPROVED by the University Dean Office.\n"
            f"Remarks: {remarks or 'All campus resources and venue bookings have been confirmed.'}\n\n"
            f"You may now publish the schedule and accept student registrations."
        )
        conn.execute(
            """INSERT INTO outbox (id, event_id, recipient, subject, message, type, status, sent_at)
               VALUES (?, ?, ?, ?, ?, 'approval_notice', 'sent', CURRENT_TIMESTAMP)""",
            (notif_id, event_id, "organiser@galgotias.edu", appr_subject, appr_body)
        )

        # Audit Log
        kavach.log_audit(
            conn,
            actor=supervisor_email,
            action="DEAN_APPROVAL_GRANTED",
            result="SUCCESS",
            event_id=event_id,
            details={"remarks": remarks, "event_name": event["name"]}
        )

        return {"success": True, "event_id": event_id, "message": f"Event '{event['name']}' successfully approved and bookings confirmed."}

def reject_event_by_supervisor(event_id: str, supervisor_email: str = "admin@galgotias.edu", reason: str = "") -> Dict[str, Any]:
    """
    Supervisor rejection action.
    Updates event status to 'rejected', cancels staged bookings,
    marks held outbox notices as 'failed', stages rejection notice to organiser,
    and logs immutable audit trail.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        event = cur.fetchone()
        if not event:
            raise ValueError(f"Event {event_id} not found.")

        # Update Event
        conn.execute(
            """UPDATE events 
               SET approval_status = 'rejected', status = 'cancelled', updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (event_id,)
        )

        # Cancel bookings
        conn.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE event_id = ?",
            (event_id,)
        )

        # Mark held outbox notices as cancelled
        conn.execute(
            "UPDATE outbox SET status = 'cancelled', error_message = ? WHERE event_id = ? AND status = 'held'",
            (f"Event request rejected: {reason}", event_id)
        )

        # Stage Rejection Notice to Organiser
        notif_id = f"notif_rej_{uuid.uuid4().hex[:8]}"
        rej_subject = f"Event Request Update: {event['name']}"
        rej_body = (
            f"Dear Organiser,\n\n"
            f"Your request for '{event['name']}' has not been approved by the Dean Office.\n"
            f"Reason: {reason or 'Administrative conflict or scheduling constraint.'}\n\n"
            f"Please revise your venue or resource requests in the Event Planner."
        )
        conn.execute(
            """INSERT INTO outbox (id, event_id, recipient, subject, message, type, status, sent_at)
               VALUES (?, ?, ?, ?, ?, 'rejection_notice', 'sent', CURRENT_TIMESTAMP)""",
            (notif_id, event_id, "organiser@galgotias.edu", rej_subject, rej_body)
        )

        # Audit Log
        kavach.log_audit(
            conn,
            actor=supervisor_email,
            action="DEAN_APPROVAL_REJECTED",
            result="REJECTED",
            event_id=event_id,
            details={"reason": reason, "event_name": event["name"]}
        )

        return {"success": True, "event_id": event_id, "message": f"Event '{event['name']}' has been rejected."}

def get_event_with_details(event_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves an event with its bookings, venue, requisitions, registrant count, and outbox logs."""
    event = fetch_one("SELECT * FROM events WHERE id = ?", (event_id,))
    if not event:
        return None

    bookings = fetch_all("SELECT * FROM bookings WHERE event_id = ?", (event_id,))
    registrations_count = fetch_one("SELECT count(*) as count FROM registrations WHERE event_id = ? AND status = 'confirmed'", (event_id,))["count"]
    waitlist_count = fetch_one("SELECT count(*) as count FROM registrations WHERE event_id = ? AND status = 'waitlisted'", (event_id,))["count"]
    outbox = fetch_all("SELECT * FROM outbox WHERE event_id = ? ORDER BY created_at DESC", (event_id,))

    return {
        "event": event,
        "bookings": bookings,
        "confirmed_attendees": registrations_count,
        "waitlisted_attendees": waitlist_count,
        "outbox": outbox
    }
