"""
Student Digital Pass & Gate Scanning API Routes.
Provides instant gate QR scanning, pass verification, and registration processing.
"""

from fastapi import APIRouter, Request, HTTPException, Depends, Query, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from typing import Dict, Any, Optional
import logging

from backend.services.pass_service import (
    get_or_create_student_profile,
    get_student_passes,
    get_personalized_recommendations_for_student
)
from backend.modules.module2_scheduling.attendee_manager import AttendeeManager
from backend.core.database.connection import fetch_one

logger = logging.getLogger(__name__)
attendee_mgr = AttendeeManager()

router = APIRouter(prefix="/api/pass", tags=["Gate Pass & Verification"])

@router.get("/scan")
async def scan_gate_pass(
    request: Request,
    reg_id: str = Query(...)
):
    """
    Gate Scanner Endpoint: Scanned via mobile camera or barcode scanner at event entry gate.
    Validates ticket and executes instant gate check-in.
    """
    # 1. Fetch registration details
    query = """
        SELECT r.id as reg_id, r.status as reg_status, r.registered_at,
               s.name as student_name, s.email as student_email, s.department as student_dept, s.year as student_year,
               e.name as event_name, e.event_type
        FROM registrations r
        JOIN students s ON r.student_id = s.id
        JOIN events e ON r.event_id = e.id
        WHERE r.id = ?
    """
    ticket = fetch_one(query, (reg_id,))

    if not ticket:
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Invalid Gate Pass - AgenticLiner</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body class="bg-light d-flex align-items-center justify-content-center" style="min-height: 100vh;">
            <div class="card p-4 text-center shadow-sm border-0" style="max-width: 380px;">
                <div class="display-1 text-danger mb-2">❌</div>
                <h4 class="fw-bold text-danger">Invalid Ticket</h4>
                <p class="text-muted small">No registration found with this QR pass ID. Entry denied.</p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=404)

    # 2. Execute Check-in
    checkin_res = attendee_mgr.check_in_attendee(reg_id)

    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        # Render clean mobile confirmation card
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Gate Entry Verified - {ticket['student_name']}</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
        </head>
        <body class="bg-light d-flex align-items-center justify-content-center p-3" style="min-height: 100vh;">
            <div class="card p-4 text-center shadow border-0 rounded-4" style="max-width: 420px; width: 100%;">
                <div class="mb-3">
                    <span class="rounded-circle bg-success text-white d-inline-flex align-items-center justify-content-center" style="width: 80px; height: 80px;">
                        <i class="bi bi-check-lg display-4"></i>
                    </span>
                </div>
                <h3 class="fw-bold text-success mb-1">ENTRY VERIFIED</h3>
                <span class="badge bg-success-subtle text-success border border-success mb-3 px-3 py-1">Gate QR Scanned Successfully</span>
                
                <div class="bg-light p-3 rounded-3 text-start mb-3 border">
                    <div class="small text-muted">Event</div>
                    <div class="fw-bold text-dark mb-2">{ticket['event_name']}</div>
                    
                    <div class="row g-2">
                        <div class="col-6">
                            <div class="small text-muted">Student Name</div>
                            <div class="fw-semibold text-dark">{ticket['student_name']}</div>
                        </div>
                        <div class="col-6">
                            <div class="small text-muted">Department</div>
                            <div class="fw-semibold text-dark">{ticket['student_dept']} (Yr {ticket['student_year']})</div>
                        </div>
                    </div>
                    
                    <div class="mt-2 pt-2 border-top">
                        <div class="small text-muted">Roll / Email</div>
                        <div class="text-dark small">{ticket['student_email']}</div>
                    </div>
                </div>

                <div class="alert alert-info py-2 small mb-0 text-start">
                    <i class="bi bi-shield-check me-1"></i> <b>Kavach Gate Security:</b> Attendance timestamp recorded in central university audit database.
                </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)

    return JSONResponse(content={"success": True, "ticket": ticket, "checkin": checkin_res})
