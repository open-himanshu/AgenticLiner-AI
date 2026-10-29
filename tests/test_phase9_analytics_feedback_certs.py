"""
Phase 9: Comprehensive Tests for Module 6 (Feedback Intelligence & Sentiment)
and Module 7 (Post-Event Analytics & Verifiable PDF Certificates with QR Verification).
"""

import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.services.analytics_service import (
    get_analytics_dashboard_data,
    record_feedback,
    issue_verifiable_certificate,
    verify_certificate_by_id
)
from backend.core.database.connection import execute_query, fetch_one

@pytest.fixture
def client():
    return TestClient(app)

def test_record_feedback_positive_sentiment():
    res = record_feedback(
        event_id="ev_001",
        rating=5,
        comment="Awesome hands-on PyTorch coding lab! High quality session.",
        student_id="stud_test_pos"
    )
    assert res["status"] == "saved"
    assert res["sentiment"] == "positive"
    assert res["sentiment_score"] > 0
    assert "content" in res["themes"]

def test_record_feedback_negative_sentiment():
    res = record_feedback(
        event_id="ev_001",
        rating=1,
        comment="Terrible sound system and delayed start in audi hall.",
        student_id="stud_test_neg"
    )
    assert res["status"] == "saved"
    assert res["sentiment"] == "negative"
    assert res["sentiment_score"] < 0
    assert any(t in ["venue", "organization"] for t in res["themes"])

def test_get_analytics_dashboard_data():
    data = get_analytics_dashboard_data()
    assert "total_reg" in data
    assert "turnout_rate" in data
    assert "sentiment_stats" in data
    assert "theme_distribution" in data
    assert "strengths" in data
    assert "concerns" in data
    assert "recent_feedback" in data
    assert isinstance(data["strengths"], list)
    assert isinstance(data["concerns"], list)
    assert data["sentiment_stats"]["positive_count"] >= 0

def test_issue_and_verify_certificate():
    # 1. Issue certificate
    cert = issue_verifiable_certificate(
        student_name="Aryan Khandelwal",
        event_id="ev_001",
        student_id="stud_aryan_01",
        verify_base_url="http://localhost:8000/verify"
    )
    cert_id = cert["certificate_id"]
    assert cert_id.startswith("CERT-2026-")
    assert Path(cert["pdf_path"]).exists()
    assert Path(cert["qr_code_path"]).exists()

    # 2. Verify certificate (first time)
    v1 = verify_certificate_by_id(cert_id)
    assert v1 is not None
    assert v1["valid"] is True
    assert v1["student_name"] == "Aryan Khandelwal"
    assert v1["verified_count"] == 1

    # 3. Verify certificate (second time: increments count)
    v2 = verify_certificate_by_id(cert_id)
    assert v2["verified_count"] == 2

    # 4. Non-existent certificate verification
    v_fake = verify_certificate_by_id("CERT-INVALID-999")
    assert v_fake is None

def test_http_feedback_and_certificate_api_endpoints(client):
    # 1. POST /api/feedback/submit
    fb_res = client.post("/api/feedback/submit", json={
        "event_id": "ev_001",
        "student_id": "stud_http_01",
        "rating": 5,
        "comment": "Outstanding technical workshop and delicious lunch!"
    })
    assert fb_res.status_code == 200
    fb_data = fb_res.json()
    assert fb_data["status"] == "saved"
    assert fb_data["analysis"]["sentiment"] == "positive"

    # 2. POST /api/certificates/generate
    gen_res = client.post("/api/certificates/generate", json={
        "student_id": "stud_http_gen",
        "student_name": "Priya Sharma",
        "event_id": "ev_001",
        "event_name": "Galgotias AI Innovation Summit"
    })
    assert gen_res.status_code == 200
    cert_data = gen_res.json()
    cert_id = cert_data["certificate_id"]
    assert "verify_url" in cert_data

    # 3. GET /api/certificates/download/{cert_id}
    down_res = client.get(f"/api/certificates/download/{cert_id}")
    assert down_res.status_code == 200
    assert down_res.headers["content-type"] == "application/pdf"
    assert len(down_res.content) > 1000

    # 4. GET /verify/{cert_id} (Web page verification)
    web_res = client.get(f"/verify/{cert_id}")
    assert web_res.status_code == 200
    assert "Priya Sharma" in web_res.text
    assert "AUTHENTIC &amp; VERIFIED CREDENTIAL" in web_res.text
    assert "GALGOTIAS UNIVERSITY" in web_res.text

    # 5. GET /verify/INVALID_ID (404 Page)
    fake_res = client.get("/verify/CERT-FAKE-00000000")
    assert fake_res.status_code == 404
    assert "CREDENTIAL NOT FOUND" in fake_res.text

def test_analytics_page_render_authenticated(client):
    # 1. Unauthenticated request should be rejected / redirected
    unauth = client.get("/analytics")
    assert unauth.status_code in [401, 307]

    # 2. Login as supervisor
    login_res = client.post("/login", json={
        "email": "admin@galgotias.edu",
        "password": "Admin@123"
    })
    assert login_res.status_code in [200, 302]

    # 3. Authenticated GET /analytics
    res = client.get("/analytics")
    assert res.status_code == 200
    assert "Feedback Intelligence &amp; Verifiable Credentials" in res.text
    assert "Sentiment Polarity Distribution" in res.text
    assert "Issue Verified Certificate" in res.text
    assert "Autonomous Post-Event AI Advisory" in res.text
