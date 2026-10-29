import pytest
import httpx
from backend.api.main import app
from backend.services.inventory_service import (
    create_venue,
    create_equipment,
    create_speaker,
    export_table_to_csv
)
from backend.core.database.connection import fetch_one

@pytest.mark.anyio
async def test_venue_creation_and_csv_export():
    # 1. Create a venue directly via service
    venue = await create_venue(
        name="Phase4 Test Auditorium",
        capacity=300,
        location="Block A, 3rd Floor",
        has_projector=True,
        has_audio=True,
        requires_special_approval=False,
        custom_image_url="/static/uploads/test_auditorium.jpg"
    )
    assert venue["name"] == "Phase4 Test Auditorium"
    assert venue["capacity"] == 300
    assert venue["image_url"] == "/static/uploads/test_auditorium.jpg"

    # Verify venue in DB
    row = fetch_one("SELECT id, name, capacity, location, image_url FROM rooms WHERE id = ?", (venue["id"],))
    assert row is not None
    assert row["name"] == "Phase4 Test Auditorium"
    assert row["capacity"] == 300
    assert row["image_url"] == "/static/uploads/test_auditorium.jpg"

    # 2. Check CSV export
    csv_str = export_table_to_csv("rooms")
    assert "id,name,capacity,location" in csv_str
    assert "Phase4 Test Auditorium" in csv_str
    assert "Block A, 3rd Floor" in csv_str

@pytest.mark.anyio
async def test_equipment_creation_and_csv_export():
    # 1. Create equipment
    eq = await create_equipment(
        name="Phase4 Collar Mic Set",
        category="equipment",
        stock=12,
        unit="mic",
        requires_approval=True,
        description="High sensitivity collar mic with receiver",
        custom_image_url="/static/uploads/collar_mic.png"
    )
    assert eq["name"] == "Phase4 Collar Mic Set"
    assert eq["stock"] == 12

    # Verify equipment in DB
    row = fetch_one("SELECT id, name, stock, requires_approval, image_url FROM resources WHERE id = ?", (eq["id"],))
    assert row is not None
    assert row["name"] == "Phase4 Collar Mic Set"
    assert row["stock"] == 12
    assert row["requires_approval"] == 1

    # 2. Check CSV export
    csv_str = export_table_to_csv("resources")
    assert "id,category,name,stock" in csv_str
    assert "Phase4 Collar Mic Set" in csv_str
    assert "equipment" in csv_str

@pytest.mark.anyio
async def test_speaker_creation_and_csv_export():
    # 1. Create speaker
    spk = await create_speaker(
        name="Dr. Jane AI Scientist",
        department="School of Computing",
        topics="Deep Learning, Robotics",
        email="jane.ai@research.edu",
        phone="9876543210",
        custom_image_url="/static/uploads/speaker_jane.jpg"
    )
    assert spk["name"] == "Dr. Jane AI Scientist"
    assert spk["department"] == "School of Computing"

    # 2. Check CSV export
    csv_str = export_table_to_csv("speakers")
    assert "id,name,department,topics,email" in csv_str
    assert "Dr. Jane AI Scientist" in csv_str

@pytest.mark.anyio
async def test_api_inventory_endpoints():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        # First authenticate as data_manager
        login_res = await client.post(
            "/login",
            data={"email": "datamanager@galgotias.edu", "password": "Data@123"},
            headers={"Accept": "text/html"}
        )
        assert login_res.status_code == 302
        assert login_res.headers["location"] == "/data-manager"

        # Form post to create a venue with HTML accept (browser submit)
        response = await client.post(
            "/api/inventory/venues",
            data={
                "name": "API Innovation Lab",
                "capacity": "60",
                "location": "Tech Tower Floor 2",
                "has_projector": "on",
                "has_audio": "on"
            },
            headers={"Accept": "text/html"}
        )
        assert response.status_code == 302
        assert "/data-manager" in response.headers.get("location", "")

        # Check it exists in rooms
        row = fetch_one("SELECT id, name FROM rooms WHERE name = 'API Innovation Lab'")
        assert row is not None
        venue_id = row["id"]

        # Delete via API
        del_resp = await client.post(f"/api/inventory/venues/{venue_id}/delete", headers={"Accept": "text/html"})
        assert del_resp.status_code == 302

        # Check it is removed
        assert fetch_one("SELECT id FROM rooms WHERE id = ?", (venue_id,)) is None

@pytest.mark.anyio
async def test_api_csv_export_downloads():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        # Authenticate as data_manager
        await client.post(
            "/login",
            data={"email": "datamanager@galgotias.edu", "password": "Data@123"},
            headers={"Accept": "text/html"}
        )

        tables = ["venues", "equipment", "speakers", "past_events", "students"]
        for t in tables:
            resp = await client.get(f"/api/inventory/export/{t}.csv")
            assert resp.status_code == 200
            assert "text/csv" in resp.headers.get("content-type", "")
            assert f"attachment; filename={t}_export.csv" in resp.headers.get("content-disposition", "")
            assert len(resp.text) > 0
