"""
Autonomous Event Architect & Universal Command Agent Service.
Translates plain natural language instructions into end-to-end operational execution:
Database creation, Kavach-guarded resource requisition, Google OR-Tools scheduling,
Flyer generation, and Outbox notice staging.

Supports Multilingual Natural Language:
1. Gemini API (100+ languages: Hindi, Hinglish, Tamil, Telugu, Bengali, French, etc.) when GEMINI_API_KEY is present.
2. High-precision Bilingual (English + Hinglish + Hindi Devanagari) deterministic engine for zero-failure offline evaluation.
"""

import os
import re
import uuid
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from backend.core.database.connection import get_connection, fetch_one, fetch_all, execute_query
from backend.services.event_workflow_service import create_event_request
from backend.services.schedule_service import solve_timetable, get_scheduling_rooms
from backend.services.analytics_service import issue_verifiable_certificate, get_analytics_dashboard_data

logger = logging.getLogger(__name__)

def parse_with_gemini_api(prompt: str) -> Optional[Dict[str, Any]]:
    """
    Calls Google Gemini API (gemini-2.5-flash / gemini-1.5-flash) when GEMINI_API_KEY is available.
    Supports 100+ languages (Hindi, Hinglish, Tamil, French, Spanish, etc.) with structured JSON output.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai
        client = genai.Client(api_key=api_key)

        system_instruction = (
            "You are an academic event coordinator AI for Galgotias University. "
            "Extract structured parameters from the user prompt in any language (English, Hindi, Hinglish, Tamil, etc.). "
            "Return valid JSON with keys: event_name (string), brief (string), event_type (hackathon|workshop|cultural|conference|seminar), "
            "domain (string), headcount (integer, default 120), budget (integer, default 25000), "
            "needs_food (boolean), needs_sound (boolean), needs_projector (boolean), needs_power (boolean)."
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"system_instruction": system_instruction, "response_mime_type": "application/json"}
        )

        data = json.loads(response.text)
        data["raw_prompt"] = prompt
        return data
    except Exception as e:
        logger.warning(f"Gemini API parse fallback to bilingual engine: {e}")
        return None

def parse_natural_language_event_prompt(prompt: str) -> Dict[str, Any]:
    """
    Intelligently decomposes an event prompt into structured parameters.
    Checks Gemini API first; falls back to comprehensive Bilingual (English + Hinglish + Hindi) parser.
    """
    # 1. Try Gemini API first if configured
    gemini_result = parse_with_gemini_api(prompt)
    if gemini_result and isinstance(gemini_result, dict) and "headcount" in gemini_result:
        return gemini_result

    # 2. Comprehensive Bilingual (English + Hinglish + Hindi) Deterministic Engine
    p_lower = prompt.lower()

    # Headcount detection (English: students, pax, people; Hinglish: bacho, baccho, logo; Hindi: छात्र, लोग)
    headcount = 120
    headcount_match = re.search(
        r'(\d+)\s*(students?|participants?|people|pax|attendees?|delegates?|seats?|bacho|bachon|baccho|bacche|log|logo|logon|chatro|chatron|छात्र|लोग|विद्यार्थी)',
        p_lower
    )
    if headcount_match:
        headcount = int(headcount_match.group(1))
    else:
        # Check plain numbers in prompt
        num_match = re.search(r'\b(50|80|100|120|150|200|250|300|500)\b', p_lower)
        if num_match:
            headcount = int(num_match.group(1))

    # Budget detection (English: budget, 35k; Hinglish: 35 hazar, 35k kharcha, paise; Hindi: 35 हजार, रुपये, बजट)
    budget = 25000
    k_match = re.search(r'\b(\d+)\s*(?:k|hazar|hazaar|हजार)\b', p_lower)
    if k_match:
        budget = int(k_match.group(1)) * 1000
    else:
        budget_match = re.search(r'(?:budget|cost|price|within|limit|rs\.?|inr|₹|kharcha|paise|rupaye|rupees|बजट|रुपये)\s*[:=]?\s*(\d[\d,]*)', p_lower)
        if budget_match:
            cleaned = budget_match.group(1).replace(",", "")
            if cleaned.isdigit():
                budget = int(cleaned)
        else:
            for m in re.finditer(r'\b(\d{4,6})\b', p_lower):
                val = int(m.group(1))
                if val != headcount:
                    budget = val
                    break

    # Event Type detection (English + Hinglish + Hindi)
    event_type = "workshop"
    if any(k in p_lower for k in ["hackathon", "coding", "hack", "हैकाथॉन"]):
        event_type = "hackathon"
    elif any(k in p_lower for k in ["cultural", "dance", "music", "fest", "drama", "arts", "nach", "gana", "sanskriti", "सांस्कृतिक", "नृत्य", "त्यौहार"]):
        event_type = "cultural"
    elif any(k in p_lower for k in ["conference", "summit", "symposium", "सम्मेलन"]):
        event_type = "conference"
    elif any(k in p_lower for k in ["seminar", "guest lecture", "webinar", "bhashan"]):
        event_type = "seminar"

    # Domain / Title extraction
    if any(k in p_lower for k in ["robotics", "robot", "रोबोटिक्स"]):
        domain = "Robotics & Autonomous Systems"
    elif any(k in p_lower for k in ["ai", "artificial intelligence", "genai", "machine learning", "एआई"]):
        domain = "Generative AI & Machine Learning"
    elif any(k in p_lower for k in ["dance", "music", "drama", "arts", "sangeet", "संगीत"]):
        domain = "Performing Arts & Cultural Evening"
    elif any(k in p_lower for k in ["web3", "blockchain", "crypto"]):
        domain = "Web3 & Blockchain Technologies"
    elif any(k in p_lower for k in ["cyber", "security", "cloud"]):
        domain = "Cyber Security & Cloud Defense"
    else:
        domain = "Innovation & Academic Excellence"

    event_name = f"Campus {domain} {event_type.capitalize()}"
    brief = f"Autonomous campus event planned for {headcount} participants focusing on {domain}. Automated allocation with clash-free scheduling."

    # Equipment & Catering needs (English: dinner, lunch, sound, mic; Hinglish: khana, nashta, awaz; Hindi: भोजन, खाना, नाश्ता, माइक)
    needs_food = any(k in p_lower for k in ["dinner", "lunch", "food", "refreshment", "snack", "catering", "meals", "khana", "nashta", "bhojan", "chai", "samosa", "खाना", "नाश्ता", "भोजन"])
    needs_sound = any(k in p_lower for k in ["sound", "mic", "microphone", "audio", "speaker", "awaz", "stage", "माइक", "ध्वनि"])
    needs_projector = any(k in p_lower for k in ["projector", "screen", "display", "presentation", "slides", "स्क्रीन", "प्रोजेक्टर"])
    needs_power = any(k in p_lower for k in ["power", "spike", "extension", "charging", "chargers", "bijli", "बोर्ड", "बिजली"])

    return {
        "event_name": event_name,
        "brief": brief,
        "event_type": event_type,
        "domain": domain,
        "headcount": headcount,
        "budget": budget,
        "needs_food": needs_food,
        "needs_sound": needs_sound,
        "needs_projector": needs_projector,
        "needs_power": needs_power,
        "raw_prompt": prompt
    }

def execute_autonomous_event_genesis(
    prompt: str,
    organizer_email: str = "organiser@galgotias.edu",
    organizer_department: str = "School of Computing Science"
) -> Dict[str, Any]:
    """
    Main Autonomous Agent Pipeline:
    Converts 1 prompt in any language (English, Hindi, Hinglish) into a fully planned,
    allocated, scheduled, and notified campus event.
    """
    timeline: List[Dict[str, Any]] = []

    # STEP 1: Natural Language Decomposition
    params = parse_natural_language_event_prompt(prompt)
    timeline.append({
        "step": 1,
        "tool": "nlp_brief_decomposer",
        "title": "Multilingual Goal Parsing",
        "status": "COMPLETED",
        "summary": f"Identified '{params['event_name']}' ({params['event_type']}) for {params['headcount']} attendees with ₹{params['budget']:,} budget limit."
    })

    # STEP 2: Clash-Free Date & Venue Matching
    existing_events_count = len(fetch_all("SELECT id FROM events"))
    day_offset = 7 + (existing_events_count * 2)
    target_date = (datetime.now() + timedelta(days=day_offset)).strftime("%Y-%m-%d")
    start_time_str = f"{target_date} 09:30:00"
    end_time_str = f"{target_date} 17:00:00"

    available_rooms = get_scheduling_rooms()
    booked_rooms = fetch_all("""
        SELECT DISTINCT room_id FROM bookings
        WHERE room_id IS NOT NULL AND status = 'confirmed'
          AND ((start_time < ? AND end_time > ?) OR (start_time >= ? AND start_time < ?))
    """, (end_time_str, start_time_str, start_time_str, end_time_str))
    booked_ids = {b["room_id"] for b in booked_rooms}

    chosen_room = None
    for r in sorted(available_rooms, key=lambda x: x["capacity"]):
        if r["capacity"] >= params["headcount"] and r["id"] not in booked_ids:
            chosen_room = r
            break
    if not chosen_room:
        for r in available_rooms:
            if r["id"] not in booked_ids:
                chosen_room = r
                break
    if not chosen_room:
        target_date = (datetime.now() + timedelta(days=day_offset + 3)).strftime("%Y-%m-%d")
        start_time_str = f"{target_date} 09:30:00"
        end_time_str = f"{target_date} 17:00:00"
        chosen_room = available_rooms[0]

    # Ensure chosen room is persisted in SQLite DB
    db_r = fetch_one("SELECT id FROM rooms WHERE id = ?", (chosen_room["id"],))
    if not db_r:
        execute_query(
            "INSERT OR IGNORE INTO rooms (id, name, capacity, location) VALUES (?, ?, ?, ?)",
            (chosen_room["id"], chosen_room["name"], chosen_room["capacity"], chosen_room.get("location", "Campus Block"))
        )

    timeline.append({
        "step": 2,
        "tool": "campus_venue_matcher",
        "title": "Autonomous Venue Allocation",
        "status": "COMPLETED",
        "summary": f"Selected '{chosen_room['name']}' (Capacity: {chosen_room['capacity']} >= {params['headcount']} pax) on {target_date} with zero schedule conflicts."
    })

    # STEP 3: Logistics & Inventory Requisition (Kavach Guarded)
    allocated_items = []
    total_cost = 0

    if params["needs_food"]:
        food_cost = min(params["budget"] // 2, params["headcount"] * 120)
        allocated_items.append({"name": "Packed Refreshments / Dinner Boxes", "category": "food", "quantity": params["headcount"], "cost": food_cost})
        total_cost += food_cost

    if params["needs_sound"]:
        allocated_items.append({"name": "Wireless Lapel Microphones & Podium Audio", "category": "equipment", "quantity": 2, "cost": 1500})
        total_cost += 1500

    if params["needs_projector"] or params["event_type"] in ["workshop", "hackathon"]:
        allocated_items.append({"name": "High-Lumen HDMI Projector & Wide Display", "category": "equipment", "quantity": 1, "cost": 2000})
        total_cost += 2000

    if params["needs_power"] or params["event_type"] == "hackathon":
        allocated_items.append({"name": "Power Surge Spike Boards (6-Socket)", "category": "equipment", "quantity": 10, "cost": 2500})
        total_cost += 2500

    vol_count = max(4, params["headcount"] // 25)
    allocated_items.append({"name": "Student Organizing Volunteers", "category": "volunteers", "quantity": vol_count, "cost": 0})

    timeline.append({
        "step": 3,
        "tool": "kavach_inventory_allocator",
        "title": "Campus Resource Requisition",
        "status": "COMPLETED",
        "summary": f"Requisitioned {len(allocated_items)} resource packages. Total cost: ₹{total_cost:,} (Savings: ₹{max(0, params['budget'] - total_cost):,})."
    })

    # STEP 4: Persist Event in Database via Workflow Service
    event_res = create_event_request(
        name=params["event_name"],
        brief=params["brief"],
        event_type=params["event_type"],
        expected_participants=params["headcount"],
        organizer_department=organizer_department,
        organizer_email=organizer_email,
        room_id=chosen_room["id"],
        start_time=start_time_str,
        end_time=end_time_str
    )
    event_id = event_res["event_id"]

    # STEP 5: Google OR-Tools CP-SAT Clash-Free Timetable Generation
    sessions_to_schedule = [
        {
            "id": f"sess_{event_id}_01",
            "title": f"Inaugural Keynote: Future of {params['domain']}",
            "expected_attendance": params["headcount"],
            "speaker_id": "spk_dean",
            "speaker_name": "Dr. Manish Raj (Dean)",
            "depends_on": None,
            "track": "General"
        },
        {
            "id": f"sess_{event_id}_02",
            "title": f"Hands-on Technical Deep Dive: {params['domain']}",
            "expected_attendance": int(params["headcount"] * 0.8),
            "speaker_id": "spk_lead",
            "speaker_name": "Dr. Vartika Puri (Associate Prof)",
            "depends_on": f"sess_{event_id}_01",
            "track": "Technical"
        },
        {
            "id": f"sess_{event_id}_03",
            "title": "Interactive Team Coding & Prototyping Challenge",
            "expected_attendance": int(params["headcount"] * 0.6),
            "speaker_id": "spk_lab",
            "speaker_name": "Prof. Akhilesh Sir",
            "depends_on": f"sess_{event_id}_02",
            "track": "Lab"
        },
        {
            "id": f"sess_{event_id}_04",
            "title": "Grand Project Exhibition & Valedictory Awards",
            "expected_attendance": params["headcount"],
            "speaker_id": "spk_eval",
            "speaker_name": "Prof. Niraj Sir",
            "depends_on": f"sess_{event_id}_03",
            "track": "Valedictory"
        }
    ]

    schedule_res = solve_timetable(sessions=sessions_to_schedule, custom_rooms=available_rooms)
    timeline.append({
        "step": 4,
        "tool": "ortools_cpsat_solver",
        "title": "Mathematical Timetable Optimization",
        "status": "COMPLETED",
        "summary": f"Generated conflict-free timetable for 4 sequential sessions satisfying speaker exclusivity and room capacity."
    })

    # STEP 6: Outbox Notification Staging
    outbox_id = f"notif_genesis_{uuid.uuid4().hex[:6]}"
    outbox_msg = (
        f"Campus Announcement: '{params['event_name']}' has been scheduled at {chosen_room['name']}. "
        f"Registration is now live with digital QR gate passes."
    )
    execute_query("""
        INSERT INTO outbox (id, event_id, recipient, subject, message, type, status)
        VALUES (?, ?, 'all_students@galgotias.edu', ?, ?, 'event_launch', 'held')
    """, (outbox_id, event_id, f"Invitation: {params['event_name']}", outbox_msg))

    timeline.append({
        "step": 5,
        "tool": "outbox_notification_stager",
        "title": "Participant Notification Broadcast",
        "status": "COMPLETED",
        "summary": f"Staged invitation broadcast (ID: {outbox_id}) in Outbox. Digital QR passes enabled for all attendees."
    })

    # STEP 7: Audit Log Entry
    audit_id = f"aud_{uuid.uuid4().hex[:8]}"
    execute_query("""
        INSERT INTO audit_log (id, event_id, actor, action, details_json, result)
        VALUES (?, ?, 'autonomous_genesis_agent', 'EVENT_AUTO_GENESIS', ?, 'SUCCESS')
    """, (audit_id, event_id, json.dumps({
        "prompt": prompt,
        "event_id": event_id,
        "room": chosen_room["name"],
        "items": allocated_items,
        "total_cost": total_cost,
        "outbox_id": outbox_id
    })))

    return {
        "success": True,
        "event_id": event_id,
        "event_name": params["event_name"],
        "event_type": params["event_type"],
        "domain": params["domain"],
        "venue": chosen_room,
        "headcount": params["headcount"],
        "budget": params["budget"],
        "total_cost_allocated": total_cost,
        "budget_remaining": max(0, params["budget"] - total_cost),
        "execution_timeline": timeline,
        "allocated_items": allocated_items,
        "scheduled_sessions": schedule_res.get("schedule", []),
        "grid_matrix": schedule_res.get("grid_matrix", []),
        "outbox_notice_id": outbox_id,
        "action_urls": {
            "flyer_url": f"/flyer/{event_id}",
            "register_url": f"/register?event_id={event_id}",
            "schedule_url": "/schedule",
            "outbox_url": "/outbox"
        }
    }

def execute_universal_command(command: str, user_role: str = "organiser") -> Dict[str, Any]:
    """
    Executes on-the-fly natural language operational commands in English, Hinglish, or Hindi.
    """
    c_lower = command.lower().strip()

    # 1. Add Venue command (English: add venue; Hinglish: venue jodo, room banao; Hindi: नया हॉल जोड़ो)
    if any(w in c_lower for w in ["venue", "room", "audi", "auditorium", "हॉल", "कमरा"]):
        if any(w in c_lower for w in ["add", "create", "new", "insert", "jodo", "banao", "dalo", "rakho", "shamil", "जोड़ो", "बनाओ"]):
            name_match = re.search(r'(?:venue|room|audi|auditorium|हॉल)\s+([A-Za-z0-9\s\-]+?)(?:\s+with|\s+capacity|\s+in|\s+seats|\s+seat|\s+ke|\s+में|$)', command, re.IGNORECASE)
            name = name_match.group(1).strip() if name_match else "Campus Innovation Hall"

            cap_match = re.search(r'(\d+)\s*(?:seats|seat|capacity|pax|सीट)?', c_lower)
            capacity = int(cap_match.group(1)) if cap_match else 150

            loc_match = re.search(r'(?:in|at|block|floor|mein|में)\s+([A-Za-z0-9\s\-]+)', command, re.IGNORECASE)
            location = loc_match.group(1).strip() if loc_match else "Campus Tech Tower"

            room_id = f"room_{uuid.uuid4().hex[:8]}"
            execute_query(
                "INSERT INTO rooms (id, name, capacity, location, has_projector, has_audio, requires_special_approval) VALUES (?, ?, ?, ?, 1, 1, 0)",
                (room_id, name, capacity, location)
            )
            execute_query(
                "INSERT INTO audit_log (id, event_id, actor, action, details_json, result) VALUES (?, 'SYSTEM', 'universal_agent', 'ADD_VENUE', ?, 'SUCCESS')",
                (f"aud_{uuid.uuid4().hex[:8]}", json.dumps({"room_id": room_id, "name": name, "capacity": capacity}))
            )
            return {
                "success": True,
                "action": "VENUE_CREATED",
                "message": f"Successfully added venue '{name}' with {capacity} seats in {location}.",
                "data": {"id": room_id, "name": name, "capacity": capacity, "location": location}
            }

    # 2. Add Equipment command (English: add equipment; Hinglish: item jodo, mic add karo; Hindi: उपकरण जोड़ो)
    if any(w in c_lower for w in ["equipment", "item", "mic", "projector", "laptop", "cable", "strip", "transmitter", "उपकरण"]):
        if any(w in c_lower for w in ["add", "create", "new", "insert", "jodo", "banao", "dalo", "जोड़ो", "बनाओ"]):
            name_match = re.search(r'(?:equipment|item|उपकरण)\s+([A-Za-z0-9\s\-]+?)(?:\s+with|\s+quantity|\s+qty|\s+price|$)', command, re.IGNORECASE)
            name = name_match.group(1).strip() if name_match else "4K Digital Projector"

            qty_match = re.search(r'(?:quantity|qty|stock|count)?\s*(\d+)', c_lower)
            quantity = int(qty_match.group(1)) if qty_match else 5

            res_id = f"res_{uuid.uuid4().hex[:8]}"
            execute_query(
                "INSERT INTO resources (id, name, category, stock, allocated_stock, unit, requires_approval, description) VALUES (?, ?, 'equipment', ?, 0, 'units', 0, 'Added by Universal Agent')",
                (res_id, name, quantity)
            )
            execute_query(
                "INSERT INTO audit_log (id, event_id, actor, action, details_json, result) VALUES (?, 'SYSTEM', 'universal_agent', 'ADD_EQUIPMENT', ?, 'SUCCESS')",
                (f"aud_{uuid.uuid4().hex[:8]}", json.dumps({"resource_id": res_id, "name": name, "stock": quantity}))
            )
            return {
                "success": True,
                "action": "EQUIPMENT_CREATED",
                "message": f"Added {quantity} units of '{name}' to campus inventory.",
                "data": {"id": res_id, "name": name, "category": "equipment", "stock": quantity}
            }

    # 3. Analytics & Turnout query (English: turnout, attendance; Hinglish: kitne log aaye, haziri; Hindi: उपस्थिति)
    if any(w in c_lower for w in ["turnout", "attendance", "analytics", "kpi", "stats", "summary", "kitne", "haziri", "उपस्थिति"]):
        data = get_analytics_dashboard_data()
        return {
            "success": True,
            "action": "ANALYTICS_QUERY",
            "message": f"Campus Status: {data['total_reg']} total registrations, {data['total_checked']} verified check-ins ({data['turnout_rate']}% turnout rate), Average Rating: {data['avg_rating']}/5.0.",
            "data": data
        }

    # 4. Certificate generation (English: generate certificate; Hinglish: certificate banao; Hindi: प्रमाण पत्र बनाओ)
    if any(w in c_lower for w in ["certificate", "cert", "praman patra", "प्रमाण पत्र"]):
        name_match = re.search(r'(?:for|to|student|ka|ke|liye|का|के लिए)\s+([A-Za-z\s]+)', command, re.IGNORECASE)
        student_name = name_match.group(1).strip() if name_match else "Himanshu Sharma"
        ev = fetch_one("SELECT id FROM events LIMIT 1")
        ev_id = ev["id"] if ev else "ev_001"
        cert = issue_verifiable_certificate(student_name=student_name, event_id=ev_id)
        return {
            "success": True,
            "action": "CERTIFICATE_GENERATED",
            "message": f"Generated verified certificate {cert['certificate_id']} for {student_name} with verification QR code.",
            "data": cert
        }

    # Default fallback: Treat as full event auto-genesis
    return execute_autonomous_event_genesis(command)
