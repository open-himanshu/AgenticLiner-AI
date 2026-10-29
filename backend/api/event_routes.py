"""
Event Lifecycle & Supervisor Approval API Routes.
Provides endpoints for creating event plans, invariant safety verification,
Dean approval / rejection, and event detail views.
"""

from fastapi import APIRouter, Request, Form, HTTPException, Depends, status
from fastapi.responses import RedirectResponse, JSONResponse
from typing import Optional, Dict, Any, List
import json
import logging

from backend.api.dependencies import require_role
from backend.services.event_workflow_service import (
    create_event_request,
    approve_event_by_supervisor,
    reject_event_by_supervisor,
    get_event_with_details
)
from backend.core.safety.kavach import InvariantViolation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["Event Lifecycle"])

@router.post("/plan")
async def create_event_plan_endpoint(
    request: Request,
    user: Dict[str, Any] = Depends(require_role(["organiser", "supervisor"]))
):
    """
    Submits a new campus event plan. Enforces Kavach invariants (room capacity, schedule overlap, equipment stock).
    Accepts both application/json and application/x-www-form-urlencoded submissions.
    """
    content_type = request.headers.get("content-type", "")
    data: Dict[str, Any] = {}

    if "application/json" in content_type:
        try:
            data = await request.json()
        except Exception:
            data = {}
    else:
        form = await request.form()
        data = dict(form)
        # Parse requisitions if passed as JSON string
        reqs_raw = data.get("requisitions")
        if reqs_raw and isinstance(reqs_raw, str):
            try:
                data["requisitions"] = json.loads(reqs_raw)
            except Exception:
                data["requisitions"] = []

    name = data.get("name")
    brief = data.get("brief", "Campus student event")
    event_type = data.get("event_type", "workshop")
    headcount = int(data.get("expected_participants") or data.get("headcount") or 100)
    organizer_dept = data.get("organizer_department", user.get("department", "School of Computing"))
    room_id = data.get("room_id")
    start_time = data.get("start_time", "2026-11-15 10:00:00")
    end_time = data.get("end_time", "2026-11-15 13:00:00")
    requisitions = data.get("requisitions", [])

    if not name:
        raise HTTPException(status_code=400, detail="Event name is required.")

    try:
        res = create_event_request(
            name=name,
            brief=brief,
            event_type=event_type,
            expected_participants=headcount,
            organizer_department=organizer_dept,
            organizer_email=user.get("email", "organiser@galgotias.edu"),
            room_id=room_id,
            start_time=start_time,
            end_time=end_time,
            requisitions=requisitions
        )

        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            redirect_target = "/supervisor?created=1" if user.get("role") == "supervisor" else "/organiser?created=1"
            return RedirectResponse(url=redirect_target, status_code=status.HTTP_302_FOUND)

        return JSONResponse(content=res)

    except InvariantViolation as iv:
        logger.warning(f"Kavach invariant violation: {iv}")
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "INVARIANT_VIOLATION",
                "rule": iv.rule,
                "item": iv.item,
                "detail": iv.detail,
                "suggestion": iv.suggestion
            }
        )
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{event_id}/approve")
async def approve_event_endpoint(
    event_id: str,
    request: Request,
    remarks: Optional[str] = Form(""),
    user: Dict[str, Any] = Depends(require_role(["supervisor"]))
):
    """
    Supervisor Dean Approval: confirms venue booking, decrements stock, releases held outbox notices.
    """
    try:
        res = approve_event_by_supervisor(
            event_id=event_id,
            supervisor_email=user.get("email", "admin@galgotias.edu"),
            remarks=remarks or ""
        )
        accept = request.headers.get("accept", "")
        if "text/html" in accept or request.headers.get("content-type") == "application/x-www-form-urlencoded":
            return RedirectResponse(url="/supervisor?approved=1", status_code=status.HTTP_302_FOUND)
        return JSONResponse(content=res)
    except Exception as e:
        logger.error(f"Error approving event: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{event_id}/reject")
async def reject_event_endpoint(
    event_id: str,
    request: Request,
    reason: Optional[str] = Form("Administrative policy constraint"),
    user: Dict[str, Any] = Depends(require_role(["supervisor"]))
):
    """
    Supervisor Dean Rejection: cancels event request, cancels bookings, sends rejection notice.
    """
    try:
        res = reject_event_by_supervisor(
            event_id=event_id,
            supervisor_email=user.get("email", "admin@galgotias.edu"),
            reason=reason or "Administrative constraint"
        )
        accept = request.headers.get("accept", "")
        if "text/html" in accept or request.headers.get("content-type") == "application/x-www-form-urlencoded":
            return RedirectResponse(url="/supervisor?rejected=1", status_code=status.HTTP_302_FOUND)
        return JSONResponse(content=res)
    except Exception as e:
        logger.error(f"Error rejecting event: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{event_id}")
async def get_event_endpoint(
    event_id: str,
    user: Dict[str, Any] = Depends(require_role(["supervisor", "organiser", "participant", "data_manager"]))
):
    """Returns event details, bookings, registrations, and outbox log."""
    details = get_event_with_details(event_id)
    if not details:
        raise HTTPException(status_code=404, detail="Event not found")
    return JSONResponse(content=details)
