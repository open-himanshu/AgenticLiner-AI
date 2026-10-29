"""
Campus Inventory & Catalog Management Service (Seller-Hub Style).
Allows coordinators and data managers to add venues, equipment, speakers, and events
with photos, categories, and details, while maintaining underlying database tables and auto-generated CSV datasets.
"""

import os
import uuid
import csv
import io
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import UploadFile

from backend.core.database.connection import get_connection, fetch_all, fetch_one, execute_query

logger = logging.getLogger(__name__)

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "static" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Default thematic placeholder graphics if no photo uploaded
DEFAULT_PLACEHOLDERS = {
    "venue": "https://images.unsplash.com/photo-1517457373958-b7bdd4587205?auto=format&fit=crop&w=600&q=80",
    "equipment": "https://images.unsplash.com/photo-1598488035139-bdbb2231ce04?auto=format&fit=crop&w=600&q=80",
    "speaker": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=600&q=80",
    "event": "https://images.unsplash.com/photo-1540575467063-178a50c2df87?auto=format&fit=crop&w=600&q=80"
}

async def save_uploaded_photo(file: Optional[UploadFile], category: str = "equipment") -> str:
    """Saves uploaded image file to static/uploads and returns relative URL path."""
    if not file or not file.filename:
        return DEFAULT_PLACEHOLDERS.get(category, DEFAULT_PLACEHOLDERS["equipment"])

    ext = Path(file.filename).suffix.lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".svg"]:
        ext = ".jpg"

    unique_filename = f"{category}_{uuid.uuid4().hex[:8]}{ext}"
    dest_path = UPLOADS_DIR / unique_filename

    content = await file.read()
    if len(content) == 0:
        return DEFAULT_PLACEHOLDERS.get(category, DEFAULT_PLACEHOLDERS["equipment"])

    with open(dest_path, "wb") as f:
        f.write(content)

    return f"/static/uploads/{unique_filename}"

# --- 1. Venues & Halls Operations ---

async def create_venue(
    name: str,
    capacity: int,
    location: str,
    has_projector: bool = True,
    has_audio: bool = True,
    requires_special_approval: bool = False,
    photo_file: Optional[UploadFile] = None,
    custom_image_url: Optional[str] = None
) -> Dict[str, Any]:
    """Adds a new campus venue with photo and capacity (like adding a venue on an inventory store)."""
    room_id = f"room_{uuid.uuid4().hex[:8]}"
    img_url = custom_image_url
    if not img_url:
        img_url = await save_uploaded_photo(photo_file, "venue")

    execute_query(
        """INSERT INTO rooms (id, name, capacity, location, has_projector, has_audio, requires_special_approval, image_url)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (room_id, name.strip(), int(capacity), location.strip(), 1 if has_projector else 0, 1 if has_audio else 0, 1 if requires_special_approval else 0, img_url)
    )

    # Log to audit trail
    execute_query(
        "INSERT INTO audit_log (id, event_id, actor, action, details_json, result) VALUES (?, ?, ?, ?, ?, ?)",
        (f"aud_{uuid.uuid4().hex[:8]}", "SYSTEM", "data_manager", "ADD_VENUE", json.dumps({"room_id": room_id, "name": name, "capacity": capacity}), "SUCCESS")
    )

    return {"id": room_id, "name": name, "capacity": capacity, "location": location, "image_url": img_url}

def delete_venue(room_id: str) -> bool:
    execute_query("DELETE FROM rooms WHERE id = ?", (room_id,))
    return True

# --- 2. Equipment & Inventory Operations ---

async def create_equipment(
    name: str,
    category: str,
    stock: int,
    unit: str = "unit",
    requires_approval: bool = False,
    description: str = "",
    photo_file: Optional[UploadFile] = None,
    custom_image_url: Optional[str] = None
) -> Dict[str, Any]:
    """Adds a new equipment/resource to catalog with photo and stock (like adding a product on Flipkart)."""
    res_id = f"res_{uuid.uuid4().hex[:8]}"
    img_url = custom_image_url
    if not img_url:
        img_url = await save_uploaded_photo(photo_file, "equipment")

    execute_query(
        """INSERT INTO resources (id, category, name, stock, allocated_stock, unit, requires_approval, description, image_url)
           VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?)""",
        (res_id, category.lower(), name.strip(), int(stock), unit.strip(), 1 if requires_approval else 0, description.strip(), img_url)
    )

    execute_query(
        "INSERT INTO audit_log (id, event_id, actor, action, details_json, result) VALUES (?, ?, ?, ?, ?, ?)",
        (f"aud_{uuid.uuid4().hex[:8]}", "SYSTEM", "data_manager", "ADD_EQUIPMENT", json.dumps({"res_id": res_id, "name": name, "stock": stock}), "SUCCESS")
    )

    return {"id": res_id, "name": name, "category": category, "stock": stock, "unit": unit, "image_url": img_url}

def delete_equipment(res_id: str) -> bool:
    execute_query("DELETE FROM resources WHERE id = ?", (res_id,))
    return True

# --- 3. Speakers & Mentors Operations ---

async def create_speaker(
    name: str,
    department: str,
    topics: str,
    email: str,
    phone: str = "",
    availability: str = "09:00-17:00",
    photo_file: Optional[UploadFile] = None,
    custom_image_url: Optional[str] = None
) -> Dict[str, Any]:
    """Adds a faculty mentor or guest speaker profile with photo and topics."""
    spk_id = f"spk_{uuid.uuid4().hex[:8]}"
    img_url = custom_image_url
    if not img_url:
        img_url = await save_uploaded_photo(photo_file, "speaker")

    avail_json = json.dumps([availability] if availability else ["09:00-17:00"])
    execute_query(
        """INSERT INTO speakers (id, name, department, topics, email, phone, availability_json, image_url)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (spk_id, name.strip(), department.strip(), topics.strip(), email.strip(), phone.strip(), avail_json, img_url)
    )

    return {"id": spk_id, "name": name, "department": department, "email": email, "image_url": img_url}

def delete_speaker(spk_id: str) -> bool:
    execute_query("DELETE FROM speakers WHERE id = ?", (spk_id,))
    return True

# --- 4. CSV Auto-Export Generator ---

def export_table_to_csv(table_name: str) -> str:
    """Exports any table from the database into a cleanly formatted CSV string."""
    valid_tables = ["rooms", "resources", "speakers", "historical_events", "students"]
    if table_name not in valid_tables:
        raise ValueError(f"Invalid table name for CSV export: {table_name}")

    rows = fetch_all(f"SELECT * FROM {table_name}")
    if not rows:
        # Return CSV header with no rows
        if table_name == "rooms":
            return "id,name,capacity,location,has_projector,has_audio,requires_special_approval,image_url\n"
        elif table_name == "resources":
            return "id,category,name,stock,allocated_stock,unit,requires_approval,description,image_url\n"
        elif table_name == "speakers":
            return "id,name,department,topics,email,phone,availability_json,image_url\n"
        elif table_name == "historical_events":
            return "id,name,event_type,organizer_department,headcount,items_used_json,feedback_score\n"
        elif table_name == "students":
            return "id,name,email,department,year,interests\n"

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
