"""
Authentication Routes for AgenticLiner.
Handles login, logout, and role-based redirects.
"""

from fastapi import APIRouter, Request, Form, HTTPException, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional

from backend.services.auth_service import authenticate_user, create_user
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

@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    """Renders the signup / registration page with role and department selection."""
    current_user = get_session_user(request)
    if current_user:
        target = ROLE_DASHBOARDS.get(current_user["role"], "/login")
        return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        request=request,
        name="signup.html",
        context={"error": None, "form_data": {}}
    )

@router.post("/signup")
async def signup_submit(
    request: Request,
    full_name: str = Form(None),
    email: str = Form(None),
    password: str = Form(None),
    confirm_password: str = Form(None),
    role: str = Form("participant"),
    department: str = Form("School of AI")
):
    """Processes user registration, role assignment, and logs them in."""
    if not email or not password:
        try:
            body = await request.json()
            full_name = body.get("full_name")
            email = body.get("email")
            password = body.get("password")
            confirm_password = body.get("confirm_password") or password
            role = body.get("role", "participant")
            department = body.get("department", "School of AI")
        except Exception:
            pass

    form_data = {
        "full_name": full_name or "",
        "email": email or "",
        "role": role or "participant",
        "department": department or "School of AI"
    }

    if not full_name or not email or not password:
        return templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={"error": "All fields are required.", "form_data": form_data}
        )

    if password != confirm_password:
        return templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={"error": "Passwords do not match.", "form_data": form_data}
        )

    try:
        user = create_user(
            email=email.strip(),
            password=password,
            role=role,
            full_name=full_name.strip(),
            department=department.strip()
        )
    except Exception as ex:
        return templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={"error": str(ex), "form_data": form_data}
        )

    # Immediately log user in with session cookie
    request.session["user"] = user
    target_url = ROLE_DASHBOARDS.get(user["role"], "/")

    accept = request.headers.get("accept", "")
    if "text/html" in accept or request.headers.get("content-type") == "application/x-www-form-urlencoded":
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
