"""
Authentication Service for AgenticLiner.
Handles password hashing with bcrypt, strong password policy verification,
one-time passwords (OTP) for signup & reset, account lockout protection, and credential checks.
"""

import bcrypt
import uuid
import re
import json
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from backend.core.database.connection import get_connection, fetch_one, execute_query

def validate_strong_password(password: str) -> Tuple[bool, Optional[str]]:
    """
    Enforces university strong password policy:
    - Minimum 8 characters
    - At least 1 uppercase letter (A-Z)
    - At least 1 lowercase letter (a-z)
    - At least 1 number (0-9)
    - At least 1 special character (!@#$%^&*()_+-=[]{}|;:,.<>?/)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter (A-Z)."
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter (a-z)."
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number (0-9)."
    if not re.search(r'[!@#$%^&*()_+=\-\[\]{}|;:,.<>?/]', password):
        return False, "Password must contain at least one special symbol (!@#$%^&* etc.)."
    return True, None

def hash_password(password: str) -> str:
    """Hashes a plain text password using bcrypt with salt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Retrieves a user by email from the users table."""
    return fetch_one("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),))

def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a user by ID from the users table."""
    return fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))

def create_user(
    email: str,
    password: str,
    role: str,
    full_name: str,
    department: str = "School of AI",
    username: Optional[str] = None
) -> Dict[str, Any]:
    """Creates a new user record with hashed password after strong password verification."""
    is_valid, err_msg = validate_strong_password(password)
    if not is_valid:
        raise ValueError(err_msg)

    valid_roles = {"supervisor", "organiser", "data_manager", "participant"}
    if role not in valid_roles:
        raise ValueError(f"Invalid role '{role}'. Allowed roles: {valid_roles}")

    existing = get_user_by_email(email)
    if existing:
        raise ValueError(f"An account with email '{email}' already exists.")

    user_id = f"usr_{uuid.uuid4().hex[:10]}"
    u_name = username or email.split("@")[0]
    p_hash = hash_password(password)

    execute_query(
        "INSERT INTO users (id, username, email, password_hash, role, full_name, department, is_verified) VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
        (user_id, u_name, email.strip().lower(), p_hash, role, full_name, department)
    )
    return {
        "id": user_id,
        "username": u_name,
        "email": email.strip().lower(),
        "role": role,
        "full_name": full_name,
        "department": department
    }

def authenticate_user(email: str, password: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Authenticates user with account lockout defense.
    Returns (user_dict, None) if successful, or (None, error_reason) if failed.
    """
    user = get_user_by_email(email)
    if not user:
        return None, "Invalid email or password."

    # Check if account is temporarily locked
    locked_until_str = user.get("locked_until")
    if locked_until_str:
        try:
            locked_dt = datetime.fromisoformat(locked_until_str)
            if datetime.now() < locked_dt:
                mins_left = int((locked_dt - datetime.now()).total_seconds() / 60) + 1
                return None, f"Account temporarily locked due to multiple failed logins. Try again in {mins_left} minute(s)."
        except Exception:
            pass

    # Verify password
    if not verify_password(password, user["password_hash"]):
        failed_count = (user.get("failed_attempts") or 0) + 1
        if failed_count >= 5:
            lockout_time = (datetime.now() + timedelta(minutes=5)).isoformat()
            execute_query(
                "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                (failed_count, lockout_time, user["id"])
            )
            return None, "Account temporarily locked for 5 minutes due to 5 consecutive failed login attempts."
        else:
            execute_query(
                "UPDATE users SET failed_attempts = ? WHERE id = ?",
                (failed_count, user["id"])
            )
            return None, f"Invalid email or password. Attempt {failed_count} of 5."

    # Login succeeded: reset failed attempts
    execute_query(
        "UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?",
        (user["id"],)
    )

    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "full_name": user["full_name"],
        "department": user.get("department") or "School of AI"
    }, None

# --- OTP Verification Engine ---

def create_otp(email: str, purpose: str, payload: Optional[Dict[str, Any]] = None) -> str:
    """
    Generates a secure 6-digit numeric OTP with 10-minute validity.
    Deletes any stale OTPs for the same email and purpose.
    """
    email_clean = email.strip().lower()
    execute_query("DELETE FROM otp_verifications WHERE email = ? AND purpose = ?", (email_clean, purpose))

    otp_id = f"otp_{uuid.uuid4().hex[:10]}"
    otp_code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = (datetime.now() + timedelta(minutes=10)).isoformat()
    payload_str = json.dumps(payload or {})

    execute_query(
        "INSERT INTO otp_verifications (id, email, otp_code, purpose, payload_json, attempts, expires_at) VALUES (?, ?, ?, ?, ?, 0, ?)",
        (otp_id, email_clean, otp_code, purpose, payload_str, expires_at)
    )
    return otp_code

def verify_otp(email: str, otp_code: str, purpose: str) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Validates the 6-digit OTP against expiration and max attempts (max 5).
    Returns (is_valid, error_message, stored_payload).
    """
    email_clean = email.strip().lower()
    record = fetch_one(
        "SELECT * FROM otp_verifications WHERE email = ? AND purpose = ? ORDER BY created_at DESC LIMIT 1",
        (email_clean, purpose)
    )
    if not record:
        return False, "No active verification code found for this email. Please request a new OTP.", None

    # Check expiration
    expires_dt = datetime.fromisoformat(record["expires_at"])
    if datetime.now() > expires_dt:
        execute_query("DELETE FROM otp_verifications WHERE id = ?", (record["id"],))
        return False, "Verification code has expired. Please request a new OTP.", None

    # Check attempt limit
    attempts = record.get("attempts", 0) + 1
    if attempts > 5:
        execute_query("DELETE FROM otp_verifications WHERE id = ?", (record["id"],))
        return False, "Too many incorrect OTP attempts. Code invalidated. Please request a new one.", None

    execute_query("UPDATE otp_verifications SET attempts = ? WHERE id = ?", (attempts, record["id"]))

    if record["otp_code"].strip() != otp_code.strip():
        remaining = 5 - attempts
        return False, f"Incorrect verification code. {remaining} attempt(s) remaining.", None

    # Success: delete record and unpack payload
    execute_query("DELETE FROM otp_verifications WHERE id = ?", (record["id"],))
    payload = json.loads(record["payload_json"] or "{}")
    return True, None, payload

def reset_user_password(email: str, new_password: str) -> Tuple[bool, Optional[str]]:
    """Updates password for verified user with strong password checks."""
    is_valid, err_msg = validate_strong_password(new_password)
    if not is_valid:
        return False, err_msg

    user = get_user_by_email(email)
    if not user:
        return False, "No account found with this email."

    new_hash = hash_password(new_password)
    execute_query(
        "UPDATE users SET password_hash = ?, failed_attempts = 0, locked_until = NULL WHERE id = ?",
        (new_hash, user["id"])
    )
    return True, None
