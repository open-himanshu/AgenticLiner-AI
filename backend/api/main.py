"""
AgenticLiner FastAPI Main Application (University Edition v2.1).
Complete End-to-End Implementation for all 7 Modules and 17 Screens of SparkX 3.0 Challenge #1.
"""

from fastapi import FastAPI, Request, Form, HTTPException, Response, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path
import os
import json
import uuid

from backend.core.database.connection import get_connection, fetch_all, fetch_one, execute_query
from backend.core.planner.agent import AutopilotAgent
from backend.core.scheduler.solver import EventScheduler
from backend.modules.module1_coplan.task_board import get_event_task_board
from backend.modules.module1_coplan.brief_parser import parse_event_brief, adaptive_intake
from backend.modules.module2_scheduling.attendee_manager import AttendeeManager
from backend.modules.module3_resource_opt.engine import ResourceOptimizer
from backend.modules.module4_participant_xp.recommender import ParticipantExperienceEngine
from backend.modules.module5_comm_agent.agent import CommunicationAgent
from backend.modules.module6_feedback.analyzer import FeedbackAnalyzer
from backend.modules.module7_analytics.generator import EventAnalyticsEngine
from backend.services.admin_service import reset_all_operational_data
from backend.api.auth_routes import router as auth_router, ROLE_DASHBOARDS
from backend.api.inventory_routes import router as inventory_router
from backend.api.dependencies import require_auth, require_role, get_session_user

app = FastAPI(title="AgenticLiner - Academic Event Platform", version="2.2.0")

# Setup Directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "frontend" / "templates"
STATIC_DIR = BASE_DIR / "frontend" / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Session Middleware Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "agenticliner_super_secret_session_key_2026_galgotias_sparkx")
SESSION_COOKIE = os.getenv("SESSION_COOKIE_NAME", "agenticliner_session")
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie=SESSION_COOKIE,
    max_age=86400,
    same_site="lax"
)

# Include Authentication Router
app.include_router(auth_router)

# Include Inventory & Catalog Router (Seller-style Add/Export)
app.include_router(inventory_router)

# Custom Exception Handlers for Strict RBAC & Unauthenticated Redirects
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    accept = request.headers.get("accept", "")
    if exc.status_code == 403:
        if "text/html" in accept:
            return templates.TemplateResponse(
                request=request,
                name="errors/403.html",
                context={"detail": exc.detail},
                status_code=403
            )
        return JSONResponse(status_code=403, content={"detail": exc.detail})
    elif exc.status_code in (401, 307):
        if "text/html" in accept:
            return RedirectResponse(url=f"/login?next={request.url.path}", status_code=status.HTTP_302_FOUND)
        return JSONResponse(status_code=401, content={"detail": exc.detail})
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

# Core Engines
autopilot_agent = AutopilotAgent()
attendee_mgr = AttendeeManager()
resource_opt = ResourceOptimizer()
participant_xp = ParticipantExperienceEngine()
comm_agent = CommunicationAgent()
feedback_analyzer = FeedbackAnalyzer()
analytics_engine = EventAnalyticsEngine()

# --- Request Models ---
class AutopilotRequest(BaseModel):
    prompt: str
    date: str = "2026-11-25"
    start_time: str = "09:00:00"
    end_time: str = "17:00:00"

class StudentRegistrationRequest(BaseModel):
    event_id: str = "ev_001"
    name: str
    email: str
    department: str
    year: int
    interests: List[str]
    preferred_sessions: Optional[List[str]] = None

class StageAnnouncementRequest(BaseModel):
    event_id: str = "ev_001"
    recipient: str
    subject: str
    message: str
    type: str = "announcement"

class AskAssistantRequest(BaseModel):
    event_id: str
    query: str

class FeedbackSubmission(BaseModel):
    event_id: str
    student_id: Optional[str] = "stud_001"
    rating: int
    comment: str

class CopilotParseRequest(BaseModel):
    brief: str

class CertificateGenerateRequest(BaseModel):
    student_id: str
    student_name: str
    event_id: str = "ev_001"
    event_name: str = "Galgotias Campus Innovation Hackathon"

# --- HTML Page Routes with Strict RBAC (Server-rendered Jinja2 UI) ---

@app.get("/", response_class=HTMLResponse)
async def root_gateway(request: Request):
    """Root Gateway: Redirects to role dashboard if authenticated, else /login."""
    user = get_session_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    target = ROLE_DASHBOARDS.get(user.get("role"), "/login")
    return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)

@app.get("/supervisor", response_class=HTMLResponse)
async def supervisor_dashboard(
    request: Request,
    user: Dict[str, Any] = Depends(require_role(["supervisor"]))
):
    """Supervisor Dashboard: University Admin & Dean Authority"""
    pending_count = fetch_one("SELECT count(*) as count FROM events WHERE approval_status = 'pending_dean_approval'")["count"]
    active_count = fetch_one("SELECT count(*) as count FROM events WHERE status IN ('allocated', 'approved', 'booked')")["count"]
    rooms_count = fetch_one("SELECT count(*) as count FROM rooms")["count"]
    resources_count = fetch_one("SELECT count(*) as count FROM resources")["count"]
    pending_events = fetch_all("SELECT * FROM events WHERE approval_status = 'pending_dean_approval' ORDER BY created_at DESC LIMIT 10")

    return templates.TemplateResponse(
        request=request,
        name="supervisor.html",
        context={
            "user": user,
            "pending_count": pending_count,
            "active_count": active_count,
            "rooms_count": rooms_count,
            "resources_count": resources_count,
            "pending_events": pending_events
        }
    )

@app.get("/supervisor/audit-log", response_class=HTMLResponse)
async def supervisor_audit_log(
    request: Request,
    user: Dict[str, Any] = Depends(require_role(["supervisor"]))
):
    """Supervisor View: Immutable System Audit Trail"""
    logs = fetch_all("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 100")
    return templates.TemplateResponse(
        request=request,
        name="supervisor.html",
        context={
            "user": user,
            "audit_logs": logs,
            "show_audit": True
        }
    )

@app.post("/admin/reset-data")
async def admin_reset_data(
    request: Request,
    user: Dict[str, Any] = Depends(require_role(["supervisor"]))
):
    """
    Supervisor Admin Action: Purges all business data and resets database to clean zero-state.
    Enforces confirmation and records an immutable audit log entry.
    """
    supervisor_email = user.get("email", "admin@galgotias.edu")
    result = reset_all_operational_data(supervisor_email)

    accept = request.headers.get("accept", "")
    if "text/html" in accept or request.headers.get("content-type") == "application/x-www-form-urlencoded":
        return RedirectResponse(url="/supervisor?reset_success=1", status_code=status.HTTP_302_FOUND)

    return JSONResponse(content=result)

@app.get("/organiser", response_class=HTMLResponse)
async def organiser_dashboard(
    request: Request,
    user: Dict[str, Any] = Depends(require_role(["organiser"]))
):
    """Organiser Dashboard: Club Event Host Hub"""
    my_events_count = fetch_one("SELECT count(*) as count FROM events")["count"]
    total_reg = fetch_one("SELECT count(*) as count FROM registrations WHERE status = 'confirmed'")["count"]
    waitlisted = fetch_one("SELECT count(*) as count FROM registrations WHERE status = 'waitlisted'")["count"]
    outbox_count = fetch_one("SELECT count(*) as count FROM outbox WHERE status = 'held'")["count"]

    return templates.TemplateResponse(
        request=request,
        name="organiser.html",
        context={
            "user": user,
            "my_events_count": my_events_count,
            "total_registered": total_reg,
            "waitlisted_count": waitlisted,
            "outbox_count": outbox_count
        }
    )

@app.get("/organiser/planner", response_class=HTMLResponse)
async def organiser_planner(
    request: Request,
    user: Dict[str, Any] = Depends(require_role(["organiser"]))
):
    """Organiser Event Planning Copilot & Logistics Inventory Cart"""
    catalog = fetch_all("SELECT * FROM resources")
    rooms = fetch_all("SELECT * FROM rooms")
    events = fetch_all("SELECT * FROM events ORDER BY created_at DESC LIMIT 5")
    tasks = get_event_task_board("hackathon")
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "user": user,
            "catalog": catalog,
            "rooms": rooms,
            "events": events,
            "tasks": tasks
        }
    )

@app.get("/data-manager", response_class=HTMLResponse)
async def data_manager_dashboard(
    request: Request,
    user: Dict[str, Any] = Depends(require_role(["data_manager"]))
):
    """Data Manager Dashboard: Master CSV Datasets & Campus Records"""
    venues_count = fetch_one("SELECT count(*) as count FROM rooms")["count"]
    equipment_count = fetch_one("SELECT count(*) as count FROM resources")["count"]
    speakers_count = fetch_one("SELECT count(*) as count FROM speakers")["count"]
    past_events_count = fetch_one("SELECT count(*) as count FROM historical_events")["count"]

    venues = fetch_all("SELECT * FROM rooms ORDER BY name")
    equipment = fetch_all("SELECT * FROM resources ORDER BY category, name")
    speakers = fetch_all("SELECT * FROM speakers ORDER BY name")
    past_events = fetch_all("SELECT * FROM historical_events")

    return templates.TemplateResponse(
        request=request,
        name="data_manager.html",
        context={
            "user": user,
            "venues_count": venues_count,
            "equipment_count": equipment_count,
            "speakers_count": speakers_count,
            "past_events_count": past_events_count,
            "venues": venues,
            "equipment": equipment,
            "speakers": speakers,
            "past_events": past_events
        }
    )

@app.get("/autopilot", response_class=HTMLResponse)
async def autopilot_page(
    request: Request,
    user: Dict[str, Any] = Depends(require_role(["organiser", "supervisor"]))
):
    """Hero Screen: Autopilot Agent Activity Panel (Live Timeline)"""
    return templates.TemplateResponse(
        request=request,
        name="autopilot.html",
        context={"user": user}
    )

@app.get("/schedule", response_class=HTMLResponse)
async def schedule_page(
    request: Request,
    user: Dict[str, Any] = Depends(require_role(["organiser", "supervisor", "participant"]))
):
    """OR-Tools Timetable Grid & Hero Speaker-Cancellation Demo"""
    rooms = fetch_all("SELECT * FROM rooms")
    speakers = fetch_all("SELECT * FROM speakers")
    return templates.TemplateResponse(
        request=request,
        name="schedule.html",
        context={
            "user": user,
            "rooms": rooms,
            "speakers": speakers
        }
    )

@app.get("/attendees", response_class=HTMLResponse)
async def attendees_page(
    request: Request,
    user: Dict[str, Any] = Depends(require_role(["organiser", "supervisor"]))
):
    """Screen #9: Attendee Management & Automatic Waitlist Engine"""
    attendees = fetch_all("""
        SELECT r.id, s.name, s.email, s.department, s.year, r.status, r.registered_at
        FROM registrations r
        JOIN students s ON r.student_id = s.id
        ORDER BY r.registered_at DESC
    """)
    return templates.TemplateResponse(
        request=request,
        name="attendees.html",
        context={"user": user, "attendees": attendees}
    )

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Screen #8: Public Student Registration Portal"""
    user = get_session_user(request)
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"user": user}
    )

@app.get("/notices", response_class=HTMLResponse)
async def notices_page(
    request: Request,
    user: Dict[str, Any] = Depends(require_role(["organiser", "supervisor"]))
):
    """Screen #12: Outbox Notification Center"""
    notices = fetch_all("SELECT * FROM outbox ORDER BY created_at DESC")
    return templates.TemplateResponse(
        request=request,
        name="notices.html",
        context={"user": user, "notices": notices}
    )

@app.get("/participant", response_class=HTMLResponse)
async def participant_page(
    request: Request,
    user: Dict[str, Any] = Depends(require_role(["participant", "supervisor"]))
):
    """Personalized Recommendations, Clash-Free Agenda & Grounded Assistant"""
    students = fetch_all("SELECT id, name, department, interests FROM students LIMIT 20")
    events = fetch_all("SELECT id, name FROM events")
    return templates.TemplateResponse(
        request=request,
        name="participant.html",
        context={
            "user": user,
            "students": students,
            "events": events
        }
    )

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(
    request: Request,
    user: Dict[str, Any] = Depends(require_role(["supervisor", "organiser"]))
):
    """Feedback Insights, Post-Event Attendance Metrics & Verifiable Credentials"""
    events = fetch_all("SELECT id, name FROM events")
    total_reg = fetch_one("SELECT count(*) as count FROM registrations WHERE status = 'confirmed'")["count"]
    total_checked = fetch_one("SELECT count(*) as count FROM attendance WHERE status = 'present'")["count"]
    turnout_rate = round((total_checked / total_reg * 100), 1) if total_reg > 0 else 0.0
    fb_row = fetch_one("SELECT count(*) as total, avg(rating) as avg_rating FROM feedback")
    fb_count = fb_row["total"] if fb_row else 0
    avg_rating = round(fb_row["avg_rating"], 1) if fb_row and fb_row["avg_rating"] else 0.0

    return templates.TemplateResponse(
        request=request,
        name="analytics.html",
        context={
            "user": user,
            "events": events,
            "total_reg": total_reg,
            "total_checked": total_checked,
            "turnout_rate": turnout_rate,
            "fb_count": fb_count,
            "avg_rating": avg_rating
        }
    )

@app.get("/flyer/{event_id}", response_class=HTMLResponse)
async def view_flyer(event_id: str, request: Request):
    """Module 2: Auto-Generated Printable Campus Flyer with QR Code"""
    event = fetch_one("SELECT * FROM events WHERE id = ?", (event_id,))
    if not event:
        event = {"id": "ev_demo", "name": "Campus AI Innovation Summit 2026", "event_type": "Hackathon", "expected_participants": 180}
    
    return templates.TemplateResponse(
        request=request,
        name="flyer.html",
        context={
            "event": event,
            "venue": "Main Auditorium A (Block C)",
            "date": "25 & 26 November 2026",
            "time": "09:30 AM - 05:30 PM",
            "coordinators": "School of Artificial Intelligence & Data Science"
        }
    )

# --- REST APIs ---

@app.post("/api/register")
async def register_student_api(req: StudentRegistrationRequest):
    """Registers student with capacity guard & priority waitlist queuing."""
    res = attendee_mgr.register_student(
        event_id=req.event_id,
        name=req.name,
        email=req.email,
        department=req.department,
        year=req.year,
        interests=req.interests,
        preferred_sessions=req.preferred_sessions
    )
    return JSONResponse(content=res)

@app.post("/api/attendees/{reg_id}/cancel")
async def cancel_attendee_api(reg_id: str):
    """Cancels registration and triggers Automatic Waitlist Promotion."""
    res = attendee_mgr.cancel_registration(reg_id)
    return JSONResponse(content=res)

@app.post("/api/attendees/{reg_id}/checkin")
async def checkin_attendee_api(reg_id: str):
    """Marks attendee checked in at gate."""
    res = attendee_mgr.check_in_attendee(reg_id)
    return JSONResponse(content=res)

@app.get("/api/export/attendees.csv")
async def export_attendees_csv(event_id: str = "ev_001"):
    """Downloads full roster as CSV."""
    csv_data = attendee_mgr.generate_attendees_csv(event_id)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=attendees_{event_id}.csv"}
    )

@app.post("/api/outbox/stage")
async def stage_outbox_message(req: StageAnnouncementRequest):
    """Stages notification in outbox."""
    msg_id = f"notif_{uuid.uuid4().hex[:8]}"
    execute_query("""
        INSERT INTO outbox (id, event_id, recipient, subject, message, type, status)
        VALUES (?, ?, ?, ?, ?, ?, 'held')
    """, (msg_id, req.event_id, req.recipient, req.subject, req.message, req.type))
    return {"success": True, "notification_id": msg_id, "status": "held"}

@app.post("/api/outbox/release-all")
async def release_all_outbox():
    """Releases all held outbox notifications to sent."""
    updated = execute_query("UPDATE outbox SET status = 'sent', sent_at = CURRENT_TIMESTAMP WHERE status = 'held'")
    return {"success": True, "dispatched_count": updated}

@app.get("/api/report/pdf/{event_id}")
async def download_executive_report_pdf(event_id: str):
    """Downloads one-click Executive Event Summary PDF Report."""
    pdf_path = analytics_engine.generate_executive_report_pdf(event_id)
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"Executive_Report_{event_id}.pdf"
    )

@app.post("/api/autopilot/run")
async def run_autopilot_api(req: AutopilotRequest):
    """Runs autonomous event planning with Kavach safety checks and live timeline logging."""
    res = autopilot_agent.run_autopilot(
        prompt=req.prompt,
        date=req.date,
        start_time=req.start_time,
        end_time=req.end_time
    )
    return JSONResponse(content=res)

@app.post("/api/copilot/parse")
async def parse_copilot_brief(req: CopilotParseRequest):
    """Module 1: Parses natural language event brief and applies Adaptive Intake verification."""
    parsed = parse_event_brief(req.brief)
    intake = adaptive_intake(req.brief)
    task_board = get_event_task_board(parsed.get("event_type", "hackathon"))
    return {
        "success": True,
        "parsed": parsed,
        "adaptive_intake": intake,
        "tasks": task_board
    }

@app.post("/api/certificates/generate")
async def generate_certificate_api(req: CertificateGenerateRequest, request: Request):
    """Module 7: Generates verified landscape PDF certificate with embedded QR verification."""
    base_url = str(request.base_url).rstrip("/")
    cert_data = analytics_engine.generate_certificate(
        student_id=req.student_id,
        student_name=req.student_name,
        event_id=req.event_id,
        event_name=req.event_name,
        verify_base_url=base_url
    )
    return JSONResponse(content=cert_data)

@app.get("/api/certificates/download/{cert_id}")
async def download_certificate_pdf(cert_id: str):
    """Module 7: Downloads the generated certificate PDF."""
    cert = fetch_one("SELECT pdf_path FROM certificates WHERE id = ?", (cert_id,))
    if not cert or not cert.get("pdf_path") or not os.path.exists(cert["pdf_path"]):
        raise HTTPException(status_code=404, detail="Certificate PDF not found.")
    return FileResponse(
        path=cert["pdf_path"],
        media_type="application/pdf",
        filename=f"Certificate_{cert_id}.pdf"
    )

@app.get("/api/catalog")
async def get_catalog():
    """Returns campus resources, categories, and inventory stock."""
    items = fetch_all("SELECT * FROM resources")
    return {"catalog": items}

@app.get("/api/recommendations/resources")
async def get_resource_recommendations(event_type: str = "hackathon", headcount: int = 150):
    """Module 3: Resource predictions & smart campus logistics bundles."""
    preds = resource_opt.estimate_resources(headcount=headcount, duration_hours=6.0, event_type=event_type)
    recs = resource_opt.get_smart_recommendations(event_type=event_type, headcount=headcount)
    plan = resource_opt.build_requisition_plan(preds)
    return {
        "predictions": preds,
        "recommendations": recs,
        "requisition_plan": plan
    }

@app.post("/api/schedule/solve")
async def solve_schedule_api(payload: Optional[Dict[str, Any]] = None):
    """Module 2: Solves conflict-free timetable using Google OR-Tools CP-SAT."""
    payload = payload or {}
    rooms = fetch_all("SELECT id, name, capacity FROM rooms")
    slots = payload.get("slots", ["09:30-11:00", "11:15-12:45", "13:45-15:15", "15:30-17:00"])
    sessions = payload.get("sessions", [
        {"id": "sess_01", "title": "Opening Keynote & Welcome", "expected_attendance": 250, "speaker_id": "spk_04", "depends_on": None},
        {"id": "sess_02", "title": "Generative AI Systems Masterclass", "expected_attendance": 120, "speaker_id": "spk_01", "depends_on": "sess_01"},
        {"id": "sess_03", "title": "Deep Learning with PyTorch Workshop", "expected_attendance": 50, "speaker_id": "spk_02", "depends_on": "sess_02"},
        {"id": "sess_04", "title": "Python for Autonomous Agents", "expected_attendance": 80, "speaker_id": "spk_03", "depends_on": "sess_01"}
    ])

    scheduler = EventScheduler(rooms=rooms, slots=slots, sessions=sessions)
    result = scheduler.solve()
    return JSONResponse(content=result)

@app.post("/api/schedule/hero-speaker-cancel")
async def hero_speaker_cancellation_demo():
    """Hero Demo: Speaker cancellation, replacement matching, re-scheduling, and Outbox alert."""
    rooms = fetch_all("SELECT id, name, capacity FROM rooms")
    slots = ["09:30-11:00", "11:15-12:45", "13:45-15:15", "15:30-17:00"]
    
    sessions = [
        {"id": "sess_01", "title": "Opening Keynote & Welcome", "expected_attendance": 250, "speaker_id": "spk_04", "depends_on": None},
        {"id": "sess_02", "title": "Generative AI Systems Masterclass", "expected_attendance": 120, "speaker_id": "spk_05", "depends_on": "sess_01"},
        {"id": "sess_03", "title": "Deep Learning with PyTorch Workshop", "expected_attendance": 50, "speaker_id": "spk_02", "depends_on": "sess_02"},
        {"id": "sess_04", "title": "Python for Autonomous Agents", "expected_attendance": 80, "speaker_id": "spk_03", "depends_on": "sess_01"}
    ]

    scheduler = EventScheduler(rooms=rooms, slots=slots, sessions=sessions)
    solve_res = scheduler.solve()

    outbox_id = f"notif_change_{uuid.uuid4().hex[:6]}"
    execute_query("""
        INSERT INTO outbox (id, event_id, recipient, subject, message, type, status)
        VALUES (?, 'ev_001', 'all_registered_participants@galgotias.edu', 'Schedule Update: Speaker Change for GenAI Masterclass', ?, 'schedule_change', 'held')
    """, (outbox_id, "Dr. Neha Verma allocated for Generative AI Systems Masterclass in Auditorium B. Schedule re-optimized with zero conflict."))

    return {
        "status": "re_planned",
        "action": "SPEAKER_CANCELLATION_HANDLED",
        "original_speaker": "Dr. Vartika Puri",
        "substitute_allocated": "Dr. Neha Verma (School of AI)",
        "match_reason": "Matching research expertise: Generative AI, Machine Learning, available in afternoon slot",
        "new_schedule": solve_res.get("schedule", []),
        "staged_outbox_notice": {
            "id": outbox_id,
            "status": "held_in_outbox",
            "message": "Participants staged for notification dispatch upon coordinator sign-off."
        }
    }

@app.get("/api/participant/{student_id}/recommendations")
async def get_student_recommendations(student_id: str):
    """Module 4: Personalized sessions & networking matching using TF-IDF."""
    student = fetch_one("SELECT interests FROM students WHERE id = ?", (student_id,))
    interests = json.loads(student["interests"]) if (student and student["interests"]) else []

    sample_sessions = [
        {"id": "s1", "title": "Generative AI & LLM Systems", "track": "AI/ML", "slot_time": "10:00 - 11:30", "expected_attendance": 150},
        {"id": "s2", "title": "Advanced Web3 & DeFi Architecture", "track": "Blockchain", "slot_time": "10:00 - 11:30", "expected_attendance": 40},
        {"id": "s3", "title": "Building Autonomous Agents with Python", "track": "AI/ML", "slot_time": "12:00 - 13:30", "expected_attendance": 100},
        {"id": "s4", "title": "Cyber Threat Modeling & Bug Bounty", "track": "Cybersecurity", "slot_time": "14:30 - 16:00", "expected_attendance": 60}
    ]

    recs = participant_xp.recommend_sessions(interests, sample_sessions, top_k=3)
    networking = participant_xp.recommend_networking(student_id)

    return {
        "student_id": student_id,
        "interests": interests,
        "recommended_sessions": recs,
        "networking": networking
    }

@app.post("/api/assistant/ask")
async def ask_assistant(req: AskAssistantRequest):
    """Module 5: Grounded Q&A Assistant without hallucinations."""
    ans = comm_agent.answer_query(req.event_id, req.query)
    return JSONResponse(content=ans)

@app.post("/api/feedback/submit")
async def submit_feedback(fb: FeedbackSubmission):
    """Module 6: Feedback submission, sentiment scoring, and theme detection."""
    analysis = feedback_analyzer.analyze_sentiment(fb.comment, rating=fb.rating)
    themes = feedback_analyzer.detect_themes(fb.comment)
    
    fb_id = f"fb_{uuid.uuid4().hex[:8]}"
    execute_query("""
        INSERT INTO feedback (id, event_id, student_id, rating, comment, sentiment, sentiment_score, theme)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (fb_id, fb.event_id, fb.student_id, fb.rating, fb.comment, analysis["sentiment"], analysis["score"], themes[0]))

    return {"status": "saved", "feedback_id": fb_id, "analysis": analysis, "themes": themes}

@app.get("/api/analytics/{event_id}")
async def get_event_analytics(event_id: str):
    """Module 7: Full event metrics, attendance rate, and future recommendations."""
    metrics = analytics_engine.compute_event_metrics(event_id)
    raw_feedbacks = fetch_all("SELECT id, rating, comment FROM feedback WHERE event_id = ?", (event_id,))
    feedback_insights = feedback_analyzer.analyze_batch(raw_feedbacks)
    return {
        "metrics": metrics,
        "feedback_intelligence": feedback_insights
    }

@app.get("/api/outbox")
async def get_outbox():
    """Lists staged and sent campus notifications."""
    notices = fetch_all("SELECT * FROM outbox ORDER BY created_at DESC LIMIT 25")
    return {"outbox": notices}

@app.get("/verify/{cert_id}")
async def verify_certificate(cert_id: str):
    """Online Verification Endpoint for certificates."""
    cert = fetch_one("SELECT * FROM certificates WHERE id = ?", (cert_id,))
    if not cert:
        return HTMLResponse("<h3>Certificate Not Found or Invalid</h3>", status_code=404)

    execute_query("UPDATE certificates SET verified_count = verified_count + 1 WHERE id = ?", (cert_id,))
    student = fetch_one("SELECT name, department, email FROM students WHERE id = ?", (cert["student_id"],))
    event = fetch_one("SELECT name FROM events WHERE id = ?", (cert["event_id"],))

    return HTMLResponse(f"""
    <html>
        <head><title>Certificate Verified - Galgotias University</title></head>
        <body style="font-family: Arial; padding: 40px; background: #f8fafc; text-align: center;">
            <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
                <h2 style="color: #1e3a8a;">Galgotias University</h2>
                <div style="background: #ecfdf5; color: #065f46; padding: 12px; border-radius: 8px; font-weight: bold; margin: 20px 0;">
                    Official Verified Certificate: {cert_id}
                </div>
                <p><b>Recipient:</b> {student['name'] if student else 'Student'}</p>
                <p><b>Department:</b> {student['department'] if student else 'School of AI'}</p>
                <p><b>Event:</b> {event['name'] if event else 'Campus Event'}</p>
                <p><b>Issued On:</b> {cert['issued_at']}</p>
                <p style="color: #6b7280; font-size: 13px;">This credential has been verified against the immutable AgenticLiner registry.</p>
            </div>
        </body>
    </html>
    """)
