"""
Authentication Service for AgenticLiner.
Handles password hashing with bcrypt, user credential verification, and user queries.
"""

import bcrypt
import uuid
from typing import Optional, Dict, Any
from backend.core.database.connection import get_connection, fetch_one, execute_query

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
    """Creates a new user record with hashed password."""
    valid_roles = {"supervisor", "organiser", "data_manager", "participant"}
    if role not in valid_roles:
        raise ValueError(f"Invalid role '{role}'. Allowed roles: {valid_roles}")

    # Check if user already exists
    existing = get_user_by_email(email)
    if existing:
        raise ValueError(f"An account with email '{email}' already exists.")

    user_id = f"usr_{uuid.uuid4().hex[:10]}"
    u_name = username or email.split("@")[0]
    p_hash = hash_password(password)

    execute_query(
        "INSERT INTO users (id, username, email, password_hash, role, full_name, department) VALUES (?, ?, ?, ?, ?, ?, ?)",
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

def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticates credentials and returns user dict without password_hash if valid."""
    user = get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None

    # Return safe user dict
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "full_name": user["full_name"],
        "department": user.get("department") or "School of AI"
    }
