"""
Authentication Routes for AgenticLiner.
Handles login, logout, and role-based redirects.
"""

from fastapi import APIRouter, Request, Form, HTTPException, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional

from backend.services.auth_service import authenticate_user
from backend.api.dependencies import get_session_user

router = APIRouter(tags=["Authentication"])

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

ROLE_DASHBOARDS = {
    "supervisor": "/supervisor",
    "organiser": "/organiser",
    "data_manager": "/data-manager",
    "participant": "/participant"
}

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: Optional[str] = None):
    """Renders the unified login page. Redirects if already authenticated."""
    current_user = get_session_user(request)
    if current_user:
        target = ROLE_DASHBOARDS.get(current_user["role"], "/login")
        return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None, "next": next or ""}
    )

@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(None),
    password: str = Form(None)
):
    """Processes login form submission or JSON payload with role-based redirect."""
    # Check if JSON payload sent
    if not email or not password:
        try:
            body = await request.json()
            email = body.get("email")
            password = body.get("password")
        except Exception:
            pass

    if not email or not password:
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={"error": "Email and password are required.", "next": ""}
            )
        raise HTTPException(status_code=400, detail="Email and password are required.")

    user = authenticate_user(email.strip(), password)
    if not user:
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={"error": "Invalid email or password. Please try again.", "next": ""}
            )
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    # Set session cookie
    request.session["user"] = user

    target_url = ROLE_DASHBOARDS.get(user["role"], "/")

    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return RedirectResponse(url=target_url, status_code=status.HTTP_302_FOUND)

    return JSONResponse(content={
        "success": True,
        "user": user,
        "redirect_url": target_url
    })

@router.get("/logout")
@router.post("/logout")
async def logout(request: Request):
    """Logs out user by clearing the session cookie and redirecting to /login."""
    request.session.clear()
    accept = request.headers.get("accept", "")
    if "text/html" in accept or request.method == "GET":
        return RedirectResponse(url="/login?logged_out=1", status_code=status.HTTP_302_FOUND)
    return JSONResponse(content={"success": True, "message": "Logged out successfully."})
