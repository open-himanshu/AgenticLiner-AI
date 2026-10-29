"""
User Seed Script for AgenticLiner.
Creates exactly ONE account per role (supervisor, organiser, data_manager, participant).
Contains NO business demo data.
"""

import sys
import os

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.core.database.connection import get_connection
from backend.services.auth_service import hash_password

SEEDED_ACCOUNTS = [
    {
        "id": "usr_supervisor_01",
        "username": "admin",
        "email": "admin@galgotias.edu",
        "password": "Admin@123",
        "role": "supervisor",
        "full_name": "University Supervisor (Dean Office)"
    },
    {
        "id": "usr_organiser_01",
        "username": "organiser",
        "email": "organiser@galgotias.edu",
        "password": "Organiser@123",
        "role": "organiser",
        "full_name": "Student Club Organiser"
    },
    {
        "id": "usr_data_mgr_01",
        "username": "datamanager",
        "email": "datamanager@galgotias.edu",
        "password": "Data@123",
        "role": "data_manager",
        "full_name": "Campus Data Operations Manager"
    },
    {
        "id": "usr_participant_01",
        "username": "student",
        "email": "student@galgotias.edu",
        "password": "Student@123",
        "role": "participant",
        "full_name": "Student Attendee"
    }
]

def seed_users(force: bool = False):
    with get_connection() as conn:
        cur = conn.cursor()
        if force:
            cur.execute("DELETE FROM users")
            print("Cleared existing users.")

        inserted = 0
        for acc in SEEDED_ACCOUNTS:
            cur.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (acc["email"],))
            existing = cur.fetchone()
            if not existing:
                p_hash = hash_password(acc["password"])
                cur.execute(
                    "INSERT INTO users (id, username, email, password_hash, role, full_name) VALUES (?, ?, ?, ?, ?, ?)",
                    (acc["id"], acc["username"], acc["email"], p_hash, acc["role"], acc["full_name"])
                )
                inserted += 1
                print(f"Created {acc['role']} account: {acc['email']}")
            else:
                print(f"Account for {acc['email']} already exists. Skipping.")

        conn.commit()
        print(f"Seed complete. {inserted} user accounts created.")

if __name__ == "__main__":
    force_flag = "--force" in sys.argv
    seed_users(force=force_flag)
