"""
Authentication & Authorization Dependencies for AgenticLiner.
Validates session cookies and enforces strict role-based access control (RBAC) on every route.
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from typing import Optional, List, Dict, Any

def get_session_user(request: Request) -> Optional[Dict[str, Any]]:
    """Retrieves user payload stored in signed session cookie."""
    return request.session.get("user")

def require_auth(request: Request) -> Dict[str, Any]:
    """Ensures user is authenticated; redirects HTML clients to /login, raises 401 for APIs."""
    user = get_session_user(request)
    if not user:
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            # Browser client: redirect to login
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": f"/login?next={request.url.path}"}
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in."
        )
    return user

def require_role(allowed_roles: List[str]):
    """
    Dependency factory ensuring user has one of the allowed roles.
    Strictly forbids cross-role access (HTTP 403).
    """
    def role_checker(request: Request) -> Dict[str, Any]:
        user = require_auth(request)
        user_role = user.get("role")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: Role '{user_role}' is not authorized to access this section."
            )
        return user
    return role_checker
