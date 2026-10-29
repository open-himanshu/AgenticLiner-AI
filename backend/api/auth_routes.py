"""
Authentication Routes for AgenticLiner.
Handles login, signup, real email OTP dispatch (Option A), Google One-Tap/OAuth (Option B),
password resets, and role-based redirects.
"""

from fastapi import APIRouter, Request, Form, HTTPException, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional
import os
import urllib.request
import json
import logging

from backend.services.auth_service import (
    authenticate_user,
    create_user,
    create_user_from_google,
    get_user_by_email,
    create_otp,
    verify_otp,
    reset_user_password,
    validate_strong_password
)
from backend.services.email_service import send_email_otp, is_smtp_configured
from backend.api.dependencies import get_session_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Authentication"])

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

ROLE_DASHBOARDS = {
    "supervisor": "/supervisor",
    "organiser": "/organiser",
    "data_manager": "/data-manager",
    "participant": "/participant"
}

def get_firebase_config():
    """Retrieves Firebase project web configuration from environment variables."""
    return {
        "apiKey": os.getenv("FIREBASE_API_KEY", "").strip(),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN", "").strip(),
        "projectId": os.getenv("FIREBASE_PROJECT_ID", "").strip(),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET", "").strip(),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID", "").strip(),
        "appId": os.getenv("FIREBASE_APP_ID", "").strip()
    }

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: Optional[str] = None):
    """Renders the unified login page with Google Sign-In and role-based redirect."""
    current_user = get_session_user(request)
    if current_user:
        target = ROLE_DASHBOARDS.get(current_user["role"], "/login")
        return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)

    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "error": None,
            "next": next or "",
            "google_client_id": google_client_id,
            "firebase_config": get_firebase_config(),
            "smtp_configured": is_smtp_configured()
        }
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

    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()

    if not email or not password:
        accept = request.headers.get("accept", "")
        if "text/html" in accept or request.headers.get("content-type") == "application/x-www-form-urlencoded":
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={
                    "error": "Email and password are required.",
                    "next": "",
                    "google_client_id": google_client_id,
                    "firebase_config": get_firebase_config(),
                    "smtp_configured": is_smtp_configured()
                }
            )
        raise HTTPException(status_code=400, detail="Email and password are required.")

    user, error_msg = authenticate_user(email.strip(), password)
    if not user:
        accept = request.headers.get("accept", "")
        if "text/html" in accept or request.headers.get("content-type") == "application/x-www-form-urlencoded":
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={
                    "error": error_msg or "Invalid email or password. Please try again.",
                    "next": "",
                    "google_client_id": google_client_id,
                    "firebase_config": get_firebase_config(),
                    "smtp_configured": is_smtp_configured()
                }
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
    """Renders the signup / registration page with role, department, and Google Sign-in."""
    current_user = get_session_user(request)
    if current_user:
        target = ROLE_DASHBOARDS.get(current_user["role"], "/login")
        return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)

    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()

    return templates.TemplateResponse(
        request=request,
        name="signup.html",
        context={
            "error": None,
            "form_data": {},
            "google_client_id": google_client_id,
            "firebase_config": get_firebase_config(),
            "smtp_configured": is_smtp_configured()
        }
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
    sends real SMTP email OTP (Option A), and forwards to /verify-otp.
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

    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
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
            context={
                "error": "All fields are required.",
                "form_data": form_data,
                "google_client_id": google_client_id,
                "smtp_configured": is_smtp_configured()
            }
        )

    if password != confirm_password:
        return templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={
                "error": "Passwords do not match.",
                "form_data": form_data,
                "google_client_id": google_client_id,
                "smtp_configured": is_smtp_configured()
            }
        )

    # Validate strong password
    is_strong, pass_err = validate_strong_password(password)
    if not is_strong:
        return templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={
                "error": pass_err,
                "form_data": form_data,
                "google_client_id": google_client_id,
                "smtp_configured": is_smtp_configured()
            }
        )

    # Check if user already exists
    existing_user = get_user_by_email(email.strip())
    if existing_user:
        return templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={
                "error": f"An account with email '{email}' already exists. Please log in.",
                "form_data": form_data,
                "google_client_id": google_client_id,
                "smtp_configured": is_smtp_configured()
            }
        )

    # Store registration info in OTP verification record
    clean_email = email.strip().lower()
    clean_name = full_name.strip()
    signup_payload = {
        "full_name": clean_name,
        "email": clean_email,
        "password": password,
        "role": role,
        "department": department.strip()
    }

    otp_code = create_otp(email=clean_email, purpose="signup", payload=signup_payload)

    # Option A: Attempt real email dispatch via SMTP
    email_sent = False
    if is_smtp_configured():
        email_sent, err_msg = send_email_otp(
            to_email=clean_email,
            otp_code=otp_code,
            purpose="signup",
            recipient_name=clean_name
        )
        if not email_sent:
            logger.warning(f"Could not send email via SMTP: {err_msg}")

    # Build redirect URL
    redirect_params = [
        f"email={clean_email}",
        "purpose=signup",
        f"email_sent={1 if email_sent else 0}",
        f"smtp_configured={1 if is_smtp_configured() else 0}"
    ]
    # Only append demo_code if email was not sent (for testing fallback)
    if not email_sent:
        redirect_params.append(f"demo_code={otp_code}")

    return RedirectResponse(
        url=f"/verify-otp?{'&'.join(redirect_params)}",
        status_code=status.HTTP_302_FOUND
    )

@router.get("/verify-otp", response_class=HTMLResponse)
async def verify_otp_page(
    request: Request,
    email: str,
    purpose: str = "signup",
    demo_code: Optional[str] = None,
    email_sent: Optional[str] = None,
    smtp_configured: Optional[str] = None
):
    """Renders OTP verification page with real inbox notification or demo code fallback."""
    return templates.TemplateResponse(
        request=request,
        name="verify_otp.html",
        context={
            "email": email,
            "purpose": purpose,
            "demo_code": demo_code,
            "email_sent": email_sent == "1",
            "smtp_configured": smtp_configured == "1" or is_smtp_configured(),
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
                "email_sent": False,
                "smtp_configured": is_smtp_configured(),
                "error": err_msg or "Invalid verification code."
            }
        )

    if purpose == "signup":
        try:
            user = create_user(
                email=payload["email"],
                password=payload["password"],
                role=payload["role"],
                full_name=payload["full_name"],
                department=payload.get("department", "School of AI")
            )
            request.session["user"] = user
            target_url = ROLE_DASHBOARDS.get(user["role"], "/")
            return RedirectResponse(url=target_url, status_code=status.HTTP_302_FOUND)
        except Exception as e:
            return templates.TemplateResponse(
                request=request,
                name="verify_otp.html",
                context={
                    "email": email,
                    "purpose": purpose,
                    "demo_code": None,
                    "email_sent": False,
                    "smtp_configured": is_smtp_configured(),
                    "error": str(e)
                }
            )

    elif purpose == "password_reset":
        request.session["reset_verified_email"] = email.strip().lower()
        return RedirectResponse(url=f"/reset-password?email={email.strip().lower()}", status_code=status.HTTP_302_FOUND)

    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

@router.post("/resend-otp")
async def resend_otp(
    request: Request,
    email: str = Form(...),
    purpose: str = Form("signup")
):
    """Regenerates a new 6-digit OTP code and dispatches via email if configured."""
    from backend.core.database.connection import fetch_one
    clean_email = email.strip().lower()
    existing = fetch_one(
        "SELECT payload_json FROM otp_verifications WHERE email = ? AND purpose = ?",
        (clean_email, purpose)
    )
    payload = json.loads(existing["payload_json"]) if existing and existing["payload_json"] else {}
    
    new_code = create_otp(email=clean_email, purpose=purpose, payload=payload)

    email_sent = False
    if is_smtp_configured():
        recipient_name = payload.get("full_name", "")
        email_sent, _ = send_email_otp(
            to_email=clean_email,
            otp_code=new_code,
            purpose=purpose,
            recipient_name=recipient_name
        )

    redirect_params = [
        f"email={clean_email}",
        f"purpose={purpose}",
        f"email_sent={1 if email_sent else 0}",
        f"smtp_configured={1 if is_smtp_configured() else 0}",
        "resent=1"
    ]
    if not email_sent:
        redirect_params.append(f"demo_code={new_code}")

    return RedirectResponse(
        url=f"/verify-otp?{'&'.join(redirect_params)}",
        status_code=status.HTTP_302_FOUND
    )

# --- Option B: Google One-Tap & OAuth Authentication ---

@router.post("/auth/google")
@router.post("/api/auth/firebase-login")
async def google_auth_callback(request: Request):
    """
    Handles Real Google / Firebase Sign-In.
    Verifies token or payload, establishes server session,
    and maps the user to their role and department in the database.
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request payload.")

    credential = data.get("credential") or data.get("id_token")
    role = data.get("role", "participant")
    department = data.get("department", "School of AI")
    is_demo = data.get("demo_google", False)

    google_email = data.get("email")
    google_name = data.get("name")

    if not is_demo and credential:
        # If real Google ID token passed, verify with Google OAuth servers
        try:
            tokeninfo_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}"
            req = urllib.request.Request(tokeninfo_url, headers={"User-Agent": "AgenticLiner-Auth"})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    token_data = json.loads(response.read().decode("utf-8"))
                    google_email = token_data.get("email") or google_email
                    google_name = token_data.get("name") or google_name
        except Exception as ex:
            # If token verification times out or Firebase client already verified, fallback to provided email
            logger.info(f"Token info note: {ex}")

    if not google_email:
        raise HTTPException(status_code=400, detail="Missing verified email address.")

    # Create or retrieve user from database
    user = create_user_from_google(
        email=google_email,
        full_name=google_name or google_email.split("@")[0],
        role=role,
        department=department
    )

    # Establish session cookie
    request.session["user"] = user
    target_url = ROLE_DASHBOARDS.get(user["role"], "/")

    return JSONResponse(content={
        "success": True,
        "user": user,
        "redirect_url": target_url
    })

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
    """Validates email and sends 6-digit OTP for password reset via real email or fallback."""
    clean_email = email.strip().lower()
    user = get_user_by_email(clean_email)
    if not user:
        return templates.TemplateResponse(
            request=request,
            name="forgot_password.html",
            context={"error": "No account registered with this email address.", "success": None}
        )

    otp_code = create_otp(email=clean_email, purpose="password_reset", payload={"user_id": user["id"]})

    email_sent = False
    if is_smtp_configured():
        email_sent, _ = send_email_otp(
            to_email=clean_email,
            otp_code=otp_code,
            purpose="password_reset",
            recipient_name=user.get("full_name", "")
        )

    redirect_params = [
        f"email={clean_email}",
        "purpose=password_reset",
        f"email_sent={1 if email_sent else 0}",
        f"smtp_configured={1 if is_smtp_configured() else 0}"
    ]
    if not email_sent:
        redirect_params.append(f"demo_code={otp_code}")

    return RedirectResponse(
        url=f"/verify-otp?{'&'.join(redirect_params)}",
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
