"""
Inventory & Catalog Management Routes (Flipkart Seller-Style Add/Edit UI).
Allows adding, viewing, deleting venues, equipment, speakers with photos,
and auto-exporting CSV datasets.
"""

from fastapi import APIRouter, Request, Form, File, UploadFile, HTTPException, Depends, Response, status
from fastapi.responses import RedirectResponse, JSONResponse, Response
from typing import Optional, Dict, Any
import logging

from backend.api.dependencies import require_role
from backend.services.inventory_service import (
    create_venue,
    delete_venue,
    create_equipment,
    delete_equipment,
    create_speaker,
    delete_speaker,
    export_table_to_csv
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/inventory", tags=["Inventory Management"])

# --- Venues ---

@router.post("/venues")
async def add_venue_endpoint(
    request: Request,
    name: str = Form(...),
    capacity: int = Form(...),
    location: str = Form("Campus Ground Floor"),
    has_projector: Optional[str] = Form(None),
    has_audio: Optional[str] = Form(None),
    requires_special_approval: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    custom_image_url: Optional[str] = Form(None),
    user: Dict[str, Any] = Depends(require_role(["data_manager", "supervisor"]))
):
    """Add a new campus venue with photo and capacity (like adding a venue product)."""
    try:
        venue = await create_venue(
            name=name,
            capacity=capacity,
            location=location,
            has_projector=bool(has_projector),
            has_audio=bool(has_audio),
            requires_special_approval=bool(requires_special_approval),
            photo_file=photo,
            custom_image_url=custom_image_url
        )
        accept = request.headers.get("accept", "")
        if "text/html" in accept or "multipart/form-data" in request.headers.get("content-type", ""):
            return RedirectResponse(url="/data-manager?tab=venues&added=1", status_code=status.HTTP_302_FOUND)
        return JSONResponse(content={"success": True, "venue": venue})
    except Exception as e:
        logger.error(f"Error adding venue: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/venues/{room_id}/delete")
async def delete_venue_endpoint(
    room_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(require_role(["data_manager", "supervisor"]))
):
    """Delete a venue from the catalog."""
    delete_venue(room_id)
    accept = request.headers.get("accept", "")
    if "text/html" in accept or request.headers.get("content-type") == "application/x-www-form-urlencoded":
        return RedirectResponse(url="/data-manager?tab=venues&deleted=1", status_code=status.HTTP_302_FOUND)
    return JSONResponse(content={"success": True, "message": f"Venue {room_id} deleted."})

# --- Equipment & Logistics Items ---

@router.post("/equipment")
async def add_equipment_endpoint(
    request: Request,
    name: str = Form(...),
    category: str = Form("equipment"),
    stock: int = Form(1),
    unit: str = Form("unit"),
    requires_approval: Optional[str] = Form(None),
    description: str = Form(""),
    photo: Optional[UploadFile] = File(None),
    custom_image_url: Optional[str] = Form(None),
    user: Dict[str, Any] = Depends(require_role(["data_manager", "supervisor"]))
):
    """Add a new logistics item to the inventory catalog with photo (Flipkart style)."""
    try:
        item = await create_equipment(
            name=name,
            category=category,
            stock=stock,
            unit=unit,
            requires_approval=bool(requires_approval),
            description=description,
            photo_file=photo,
            custom_image_url=custom_image_url
        )
        accept = request.headers.get("accept", "")
        if "text/html" in accept or "multipart/form-data" in request.headers.get("content-type", ""):
            return RedirectResponse(url="/data-manager?tab=equipment&added=1", status_code=status.HTTP_302_FOUND)
        return JSONResponse(content={"success": True, "equipment": item})
    except Exception as e:
        logger.error(f"Error adding equipment: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/equipment/{res_id}/delete")
async def delete_equipment_endpoint(
    res_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(require_role(["data_manager", "supervisor"]))
):
    """Delete an equipment item from catalog."""
    delete_equipment(res_id)
    accept = request.headers.get("accept", "")
    if "text/html" in accept or request.headers.get("content-type") == "application/x-www-form-urlencoded":
        return RedirectResponse(url="/data-manager?tab=equipment&deleted=1", status_code=status.HTTP_302_FOUND)
    return JSONResponse(content={"success": True, "message": f"Equipment {res_id} deleted."})

# --- Speakers ---

@router.post("/speakers")
async def add_speaker_endpoint(
    request: Request,
    name: str = Form(...),
    department: str = Form("School of AI"),
    topics: str = Form("AI, ML"),
    email: str = Form(...),
    phone: str = Form(""),
    availability: str = Form("09:00-17:00"),
    photo: Optional[UploadFile] = File(None),
    custom_image_url: Optional[str] = Form(None),
    user: Dict[str, Any] = Depends(require_role(["data_manager", "supervisor"]))
):
    """Add a guest speaker or faculty mentor with photo and availability."""
    try:
        speaker = await create_speaker(
            name=name,
            department=department,
            topics=topics,
            email=email,
            phone=phone,
            availability=availability,
            photo_file=photo,
            custom_image_url=custom_image_url
        )
        accept = request.headers.get("accept", "")
        if "text/html" in accept or "multipart/form-data" in request.headers.get("content-type", ""):
            return RedirectResponse(url="/data-manager?tab=speakers&added=1", status_code=status.HTTP_302_FOUND)
        return JSONResponse(content={"success": True, "speaker": speaker})
    except Exception as e:
        logger.error(f"Error adding speaker: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/speakers/{spk_id}/delete")
async def delete_speaker_endpoint(
    spk_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(require_role(["data_manager", "supervisor"]))
):
    """Delete a speaker from the directory."""
    delete_speaker(spk_id)
    accept = request.headers.get("accept", "")
    if "text/html" in accept or request.headers.get("content-type") == "application/x-www-form-urlencoded":
        return RedirectResponse(url="/data-manager?tab=speakers&deleted=1", status_code=status.HTTP_302_FOUND)
    return JSONResponse(content={"success": True, "message": f"Speaker {spk_id} deleted."})

# --- Automatic CSV Export Endpoint ---

@router.get("/export/{table_name}.csv")
async def export_csv_endpoint(
    table_name: str,
    user: Dict[str, Any] = Depends(require_role(["data_manager", "supervisor", "organiser"]))
):
    """Auto-generates and downloads current table records as a clean CSV file."""
    # Map common aliases
    alias_map = {
        "venues": "rooms",
        "equipment": "resources",
        "speakers": "speakers",
        "past_events": "historical_events",
        "students": "students"
    }
    actual_table = alias_map.get(table_name, table_name)
    try:
        csv_data = export_table_to_csv(actual_table)
        filename = f"{table_name}_export.csv"
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
