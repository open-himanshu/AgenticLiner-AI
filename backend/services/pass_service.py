"""
Student Participant & Digital QR Gate Pass Service.
Manages student event passes, scannable QR code generation, gate verification,
and personalized agenda recommendations.
"""

import io
import json
import base64
import uuid
import qrcode
from typing import Dict, Any, List, Optional

from backend.core.database.connection import get_connection, fetch_one, fetch_all, execute_query
from backend.modules.module4_participant_xp.recommender import ParticipantExperienceEngine

participant_xp = ParticipantExperienceEngine()

def generate_qr_base64(payload_text: str) -> str:
    """Generates a clean base64 data URI of a QR code image."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2
    )
    qr.add_data(payload_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_data}"

def get_or_create_student_profile(email: str, name: str = "Student Participant", department: str = "Computer Science", year: int = 2) -> Dict[str, Any]:
    """Retrieves student record or automatically provisions one for the logged in user."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM students WHERE email = ?", (email,))
        row = cur.fetchone()
        if row:
            student = dict(row)
            try:
                student["interests_list"] = json.loads(student["interests"]) if student.get("interests") else []
            except Exception:
                student["interests_list"] = [s.strip() for s in (student.get("interests") or "").split(",") if s.strip()]
            return student

        # Auto-provision student profile
        stud_id = f"stud_{uuid.uuid4().hex[:6]}"
        default_interests = ["Artificial Intelligence", "Python", "Hackathons", "Web Development"]
        conn.execute(
            """INSERT INTO students (id, name, email, department, year, interests)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (stud_id, name, email, department, year, json.dumps(default_interests))
        )
        return {
            "id": stud_id,
            "name": name,
            "email": email,
            "department": department,
            "year": year,
            "interests": json.dumps(default_interests),
            "interests_list": default_interests
        }

def get_student_passes(email: str, base_url: str = "http://127.0.0.1:8000") -> List[Dict[str, Any]]:
    """
    Returns all event registrations for this student, complete with
    event details, allocated venue, status, and live scannable QR gate passes.
    """
    student = get_or_create_student_profile(email)
    student_id = student["id"]

    query = """
        SELECT r.id as reg_id, r.status as reg_status, r.registered_at,
               e.id as event_id, e.name as event_name, e.brief as event_brief, e.event_type,
               (SELECT rm.name FROM bookings b JOIN rooms rm ON b.room_id = rm.id WHERE b.event_id = e.id LIMIT 1) as venue_name,
               (SELECT count(*) FROM attendance a WHERE a.student_id = ? AND a.session_id IN (SELECT id FROM sessions WHERE event_id = e.id)) as is_checked_in
        FROM registrations r
        JOIN events e ON r.event_id = e.id
        WHERE r.student_id = ?
        ORDER BY r.registered_at DESC
    """
    rows = fetch_all(query, (student_id, student_id))

    passes = []
    for row in rows:
        reg_id = row["reg_id"]
        # Gate check-in verification URL for the QR scanner
        verify_url = f"{base_url}/api/pass/scan?reg_id={reg_id}"
        qr_code_uri = generate_qr_base64(verify_url)

        item = dict(row)
        item["qr_code_uri"] = qr_code_uri
        item["verify_url"] = verify_url
        item["venue_name"] = item.get("venue_name") or "Main Campus Ground"
        passes.append(item)

    return passes

def get_personalized_recommendations_for_student(student: Dict[str, Any]) -> Dict[str, Any]:
    """
    Uses Module 4 TF-IDF recommender to calculate personalized sessions
    and peer networking based on student's registered interests.
    """
    interests = student.get("interests_list", [])

    sample_sessions = [
        {"id": "s1", "title": "Generative AI Systems & Agentic Workflows", "track": "Artificial Intelligence", "slot_time": "10:00 AM - 11:30 AM", "expected_attendance": 150},
        {"id": "s2", "title": "Full-Stack Web3 & Smart Contracts Architecture", "track": "Blockchain", "slot_time": "11:45 AM - 01:15 PM", "expected_attendance": 60},
        {"id": "s3", "title": "Production Python for Autonomous AI Agents", "track": "Artificial Intelligence", "slot_time": "02:00 PM - 03:30 PM", "expected_attendance": 120},
        {"id": "s4", "title": "Cloud Native Microservices & Kubernetes", "track": "Cloud Computing", "slot_time": "03:45 PM - 05:00 PM", "expected_attendance": 80},
        {"id": "s5", "title": "Hands-On Ethical Hacking & Red Teaming", "track": "Cybersecurity", "slot_time": "02:00 PM - 03:30 PM", "expected_attendance": 90}
    ]

    recs = participant_xp.recommend_sessions(interests, sample_sessions, top_k=3)
    peers = participant_xp.recommend_networking(student["id"])

    return {
        "recommended_sessions": recs,
        "recommended_peers": peers
    }
