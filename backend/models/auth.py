"""
Authentication and User Pydantic Models.
"""

from pydantic import BaseModel, EmailStr
from enum import Enum
from typing import Optional

class UserRole(str, Enum):
    SUPERVISOR = "supervisor"
    ORGANISER = "organiser"
    DATA_MANAGER = "data_manager"
    PARTICIPANT = "participant"

class LoginRequest(BaseModel):
    email: str
    password: str

class UserSession(BaseModel):
    id: str
    username: str
    email: str
    role: UserRole
    full_name: str
