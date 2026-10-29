"""
Unit tests for Module 7: Event Analytics & Verifiable Certificate Generator.
"""
import pytest
import os
from pathlib import Path
from backend.modules.module7_analytics.generator import EventAnalyticsEngine
from backend.core.database.connection import get_connection

def test_certificate_generation():
    engine = EventAnalyticsEngine()
    
    # Ensure event exists in db
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO events (id, name, brief) VALUES ('ev_001', 'SparkX 3.0 Hackathon', 'Hackathon event')"
        )

    res = engine.generate_certificate(
        student_name="Himanshu",
        event_name="SparkX 3.0 Hackathon",
        student_id="stud_001",
        event_id="ev_001"
    )

    assert "CERT-2026-" in res["certificate_id"]
    assert Path(res["pdf_path"]).exists()
    assert Path(res["qr_code_path"]).exists()

    # Clean up generated test files
    try:
        os.remove(res["pdf_path"])
        os.remove(res["qr_code_path"])
    except OSError:
        pass
