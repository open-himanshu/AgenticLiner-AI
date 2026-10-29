"""
Admin Operations Service for AgenticLiner.
Handles master database reset, zero-state purging, and supervisor administrative maintenance.
"""

import logging
from typing import Dict, Any
from backend.core.database.connection import get_connection, execute_query
from backend.services.seed_users import seed_users

logger = logging.getLogger(__name__)

ALL_OPERATIONAL_TABLES = [
    "certificates",
    "feedback",
    "attendance",
    "registrations",
    "bookings",
    "sessions",
    "rooms",
    "speakers",
    "resources",
    "students",
    "historical_events",
    "events",
    "outbox",
    "audit_log",
    "otp_verifications"
]

def reset_all_operational_data(supervisor_email: str = "admin@galgotias.edu") -> Dict[str, Any]:
    """
    Purges all operational and business data from the database.
    Restores the system to a clean, empty state with 0 counts.
    Preserves and ensures core role user accounts.
    """
    logger.info(f"Initiating full database reset requested by {supervisor_email}")
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = OFF;")
        
        for table in ALL_OPERATIONAL_TABLES:
            try:
                cursor.execute(f"DELETE FROM {table};")
            except Exception as e:
                logger.warning(f"Could not purge table {table}: {e}")
                
        cursor.execute("PRAGMA foreign_keys = ON;")
        conn.commit()

    # Re-seed the 4 essential role user accounts
    seed_users(force=False)

    # Insert an immutable audit trail entry documenting the reset action
    audit_id = "aud_reset_001"
    try:
        execute_query(
            """INSERT INTO audit_log (id, event_id, actor, action, details_json, result)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (audit_id, "SYSTEM", supervisor_email, "ADMIN_RESET_ALL_DATA", '{"scope": "All operational tables purged to zero-state"}', "SUCCESS")
        )
    except Exception as e:
        logger.warning(f"Could not record reset in audit log: {e}")

    return {
        "success": True,
        "message": "All operational datasets successfully purged to clean zero-state.",
        "tables_purged": ALL_OPERATIONAL_TABLES
    }
