"""
Tool definitions for AgenticLiner Autopilot Agent (Academic Operations).
All state mutations are checked and guarded by the Kavach Safety Engine.
"""

import json
import uuid
from typing import Dict, Any, List, Optional
from backend.core.database.connection import get_connection
from backend.core.safety.kavach import KavachEngine, InvariantViolation
from backend.modules.module3_resource_opt.engine import ResourceOptimizer
from backend.modules.module1_coplan.brief_parser import adaptive_intake, parse_event_brief

kavach = KavachEngine()
resource_opt = ResourceOptimizer()

def tool_find_free_venues(min_capacity: int, date: str, start_time: str, end_time: str) -> Dict[str, Any]:
    """Finds all campus rooms that are not booked and have at least min_capacity seats."""
    start_dt = f"{date} {start_time}" if " " not in start_time else start_time
    end_dt = f"{date} {end_time}" if " " not in end_time else end_time

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT r.id, r.name, r.capacity, r.location, r.has_projector, r.has_audio, r.requires_special_approval
            FROM rooms r
            WHERE r.capacity >= ?
              AND r.id NOT IN (
                  SELECT DISTINCT b.room_id 
                  FROM bookings b 
                  WHERE b.room_id IS NOT NULL 
                    AND b.status = 'confirmed'
                    AND (
                        (b.start_time < ? AND b.end_time > ?) OR
                        (b.start_time >= ? AND b.start_time < ?)
                    )
              )
            ORDER BY r.capacity ASC
        """, (min_capacity, end_dt, start_dt, start_dt, end_dt))
        available = [dict(row) for row in cur.fetchall()]
        return {
            "success": True,
            "min_capacity_requested": min_capacity,
            "available_venues_count": len(available),
            "venues": available
        }

def tool_check_equipment(category: Optional[str] = None) -> Dict[str, Any]:
    """Lists current campus logistics inventory with available stock."""
    with get_connection() as conn:
        cur = conn.cursor()
        if category:
            cur.execute("SELECT id, category, name, stock, allocated_stock, unit, requires_approval, description FROM resources WHERE category = ?", (category,))
        else:
            cur.execute("SELECT id, category, name, stock, allocated_stock, unit, requires_approval, description FROM resources")
        items = [dict(row) for row in cur.fetchall()]
        return {"items": items, "count": len(items)}

def tool_recommend_from_history(event_type: str, headcount: int) -> Dict[str, Any]:
    """Provides historical and campus safety recommendations."""
    preds = resource_opt.estimate_resources(headcount=headcount, duration_hours=4.0, event_type=event_type)
    recs = resource_opt.get_smart_recommendations(event_type=event_type, headcount=headcount)
    return {
        "event_type": event_type,
        "headcount": headcount,
        "estimates": preds["predicted_needs"],
        "recommendations": recs
    }

def tool_requisition_campus_resources(event_id: str, room_id: str, attendance: int, items_json: str, date: str, start_time: str, end_time: str) -> Dict[str, Any]:
    """
    Executes campus venue and inventory allocations inside a Kavach transaction savepoint.
    Enforces room capacity, room overlap, and inventory stock invariants.
    """
    start_dt = f"{date} {start_time}" if " " not in start_time else start_time
    end_dt = f"{date} {end_time}" if " " not in end_time else end_time

    try:
        items = json.loads(items_json) if isinstance(items_json, str) else items_json
    except Exception:
        items = []

    def perform_allocation_transaction(conn: Any):
        # 1. Invariant verification
        kavach.verify_room_capacity(conn, room_id, attendance)
        kavach.verify_room_overlap(conn, room_id, start_dt, end_dt)

        cur = conn.cursor()
        cur.execute("SELECT name, requires_special_approval FROM rooms WHERE id = ?", (room_id,))
        room = cur.fetchone()
        room_name = room["name"] if room else room_id
        room_approval = "pending_dean_approval" if room["requires_special_approval"] else "auto_approved"

        # 2. Allocate Venue
        room_booking_id = f"bk_{uuid.uuid4().hex[:8]}"
        conn.execute("""
            INSERT INTO bookings (id, event_id, room_id, item_name, category, start_time, end_time, quantity, approval_status, status)
            VALUES (?, ?, ?, ?, 'venue', ?, ?, 1, ?, 'confirmed')
        """, (room_booking_id, event_id, room_id, room_name, start_dt, end_dt, room_approval))

        allocated_details = [{"type": "venue", "name": room_name, "id": room_id, "approval": room_approval}]

        # 3. Allocate Resources & Equipment
        for it in items:
            res_id = it.get("resource_id")
            qty = it.get("quantity", 1)
            kavach.verify_resource_stock(conn, res_id, qty, start_dt, end_dt)
            
            cur.execute("SELECT name, category, requires_approval FROM resources WHERE id = ?", (res_id,))
            r_data = cur.fetchone()
            if r_data:
                item_approval = "pending_dean_approval" if r_data["requires_approval"] else "auto_approved"
                b_id = f"bk_{uuid.uuid4().hex[:8]}"
                conn.execute("""
                    INSERT INTO bookings (id, event_id, resource_id, item_name, category, start_time, end_time, quantity, approval_status, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed')
                """, (b_id, event_id, res_id, r_data["name"], r_data["category"], start_dt, end_dt, qty, item_approval))
                
                # Update allocated stock
                conn.execute("UPDATE resources SET allocated_stock = allocated_stock + ? WHERE id = ?", (qty, res_id))
                allocated_details.append({"type": r_data["category"], "name": r_data["name"], "quantity": qty, "approval": item_approval})

        # Update event status
        conn.execute("UPDATE events SET status = 'allocated' WHERE id = ?", (event_id,))

        # Stage confirmation outbox notice
        outbox_id = f"notif_{uuid.uuid4().hex[:8]}"
        conn.execute("""
            INSERT INTO outbox (id, event_id, recipient, subject, message, type, status)
            VALUES (?, ?, 'event.coordinator@galgotiasuniversity.edu.in', 'Campus Logistics Allocated', ?, 'confirmation', 'held')
        """, (outbox_id, event_id, f"Successfully allocated {room_name} and {len(items)} campus resource items."))

        return {
            "room_booking_id": room_booking_id,
            "room_name": room_name,
            "allocated_items": allocated_details,
            "total_items": len(allocated_details)
        }

    with get_connection() as conn:
        result = kavach.execute_with_kavach(
            conn, event_id, "autopilot_agent", "requisition_campus_resources", perform_allocation_transaction
        )
        return result
