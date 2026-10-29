"""
Authentication Routes for AgenticLiner.
Handles login, signup, email OTP verification, password resets, and role-based redirects.
"""

from fastapi import APIRouter, Request, Form, HTTPException, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional

from backend.services.auth_service import (
    authenticate_user,
    create_user,
    get_user_by_email,
    create_otp,
    verify_otp,
    reset_user_password,
    validate_strong_password
)
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
    if not email or not password:
        try:
            body = await request.json()
            email = body.get("email")
            password = body.get("password")
        except Exception:
            pass

    if not email or not password:
        accept = request.headers.get("accept", "")
        if "text/html" in accept or request.headers.get("content-type") == "application/x-www-form-urlencoded":
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={"error": "Email and password are required.", "next": ""}
            )
        raise HTTPException(status_code=400, detail="Email and password are required.")

    user, error_msg = authenticate_user(email.strip(), password)
    if not user:
        accept = request.headers.get("accept", "")
        if "text/html" in accept or request.headers.get("content-type") == "application/x-www-form-urlencoded":
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={"error": error_msg or "Invalid email or password. Please try again.", "next": ""}
            )
        raise HTTPException(status_code=401, detail=error_msg or "Invalid credentials.")

    # Set session cookie
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
    """
    Validates user registration, verifies strong password,
    creates OTP for email verification, and forwards to /verify-otp.
    """
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

    # Validate strong password
    is_strong, pass_err = validate_strong_password(password)
    if not is_strong:
        return templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={"error": pass_err, "form_data": form_data}
        )

    # Check if user already exists
    existing_user = get_user_by_email(email.strip())
    if existing_user:
        return templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={"error": f"An account with email '{email}' already exists. Please log in.", "form_data": form_data}
        )

    # Store registration info in OTP verification record
    signup_payload = {
        "full_name": full_name.strip(),
        "email": email.strip().lower(),
        "password": password,
        "role": role,
        "department": department.strip()
    }

    otp_code = create_otp(email=email.strip(), purpose="signup", payload=signup_payload)

    # In production/demo, redirect to OTP verification screen with simulated OTP banner
    return RedirectResponse(
        url=f"/verify-otp?email={email.strip().lower()}&purpose=signup&demo_code={otp_code}",
        status_code=status.HTTP_302_FOUND
    )

@router.get("/verify-otp", response_class=HTMLResponse)
async def verify_otp_page(
    request: Request,
    email: str,
    purpose: str = "signup",
    demo_code: Optional[str] = None
):
    """Renders OTP verification page with 6-digit input and demo OTP notification."""
    return templates.TemplateResponse(
        request=request,
        name="verify_otp.html",
        context={
            "email": email,
            "purpose": purpose,
            "demo_code": demo_code,
            "error": None
        }
    )

@router.post("/verify-otp")
async def verify_otp_submit(
    request: Request,
    email: str = Form(...),
    purpose: str = Form("signup"),
    otp_code: str = Form(...)
):
    """Verifies the 6-digit OTP. On success, completes user registration or password reset."""
    is_valid, err_msg, payload = verify_otp(email=email.strip(), otp_code=otp_code.strip(), purpose=purpose)
    
    if not is_valid:
        return templates.TemplateResponse(
            request=request,
            name="verify_otp.html",
            context={
                "email": email,
                "purpose": purpose,
                "demo_code": None,
                "error": err_msg or "Invalid verification code."
            }
        )

    if purpose == "signup":
        # Create user account in database
        try:
            user = create_user(
                email=payload["email"],
                password=payload["password"],
                role=payload["role"],
                full_name=payload["full_name"],
                department=payload.get("department", "School of AI")
            )
            # Log in the user
            request.session["user"] = user
            target_url = ROLE_DASHBOARDS.get(user["role"], "/")
            return RedirectResponse(url=target_url, status_code=status.HTTP_302_FOUND)
        except Exception as e:
            return templates.TemplateResponse(
                request=request,
                name="verify_otp.html",
                context={"email": email, "purpose": purpose, "demo_code": None, "error": str(e)}
            )

    elif purpose == "password_reset":
        # Authorize password reset by creating temporary session reset flag
        request.session["reset_verified_email"] = email.strip().lower()
        return RedirectResponse(url=f"/reset-password?email={email.strip().lower()}", status_code=status.HTTP_302_FOUND)

    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

@router.post("/resend-otp")
async def resend_otp(
    request: Request,
    email: str = Form(...),
    purpose: str = Form("signup")
):
    """Regenerates a new 6-digit OTP code."""
    # Retrieve existing payload if available
    from backend.core.database.connection import fetch_one
    existing = fetch_one(
        "SELECT payload_json FROM otp_verifications WHERE email = ? AND purpose = ?",
        (email.strip().lower(), purpose)
    )
    import json
    payload = json.loads(existing["payload_json"]) if existing and existing["payload_json"] else {}
    
    new_code = create_otp(email=email.strip(), purpose=purpose, payload=payload)
    return RedirectResponse(
        url=f"/verify-otp?email={email.strip().lower()}&purpose={purpose}&demo_code={new_code}&resent=1",
        status_code=status.HTTP_302_FOUND
    )

@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Renders forgot password request form."""
    return templates.TemplateResponse(
        request=request,
        name="forgot_password.html",
        context={"error": None, "success": None}
    )

@router.post("/forgot-password")
async def forgot_password_submit(
    request: Request,
    email: str = Form(...)
):
    """Validates email and sends 6-digit OTP for password reset."""
    user = get_user_by_email(email.strip())
    if not user:
        return templates.TemplateResponse(
            request=request,
            name="forgot_password.html",
            context={"error": "No account registered with this email address.", "success": None}
        )

    otp_code = create_otp(email=email.strip(), purpose="password_reset", payload={"user_id": user["id"]})
    return RedirectResponse(
        url=f"/verify-otp?email={email.strip().lower()}&purpose=password_reset&demo_code={otp_code}",
        status_code=status.HTTP_302_FOUND
    )

@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, email: str):
    """Renders set new password page for verified user."""
    verified_email = request.session.get("reset_verified_email")
    if not verified_email or verified_email.lower() != email.strip().lower():
        return RedirectResponse(url="/forgot-password?error=unauthorized", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        request=request,
        name="reset_password.html",
        context={"email": email, "error": None}
    )

@router.post("/reset-password")
async def reset_password_submit(
    request: Request,
    email: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...)
):
    """Applies strong password checks and updates password hash."""
    verified_email = request.session.get("reset_verified_email")
    if not verified_email or verified_email.lower() != email.strip().lower():
        return RedirectResponse(url="/forgot-password", status_code=status.HTTP_302_FOUND)

    if new_password != confirm_password:
        return templates.TemplateResponse(
            request=request,
            name="reset_password.html",
            context={"email": email, "error": "Passwords do not match."}
        )

    success, err_msg = reset_user_password(email.strip(), new_password)
    if not success:
        return templates.TemplateResponse(
            request=request,
            name="reset_password.html",
            context={"email": email, "error": err_msg or "Failed to reset password."}
        )

    # Clear reset flag from session
    request.session.pop("reset_verified_email", None)
    return RedirectResponse(url="/login?reset_success=1", status_code=status.HTTP_302_FOUND)

@router.get("/logout")
@router.post("/logout")
async def logout(request: Request):
    """Logs out user by clearing the session cookie and redirecting to /login."""
    request.session.clear()
    accept = request.headers.get("accept", "")
    if "text/html" in accept or request.method == "GET":
        return RedirectResponse(url="/login?logged_out=1", status_code=status.HTTP_302_FOUND)
    return JSONResponse(content={"success": True, "message": "Logged out successfully."})
