import sys
import os

# Ensure root path
sys.path.insert(0, os.path.abspath("."))

from backend.modules.module1_coplan.brief_parser import parse_event_brief, adaptive_intake
from backend.modules.module1_coplan.task_board import get_event_task_board
from backend.core.scheduler.solver import EventScheduler
from backend.modules.module2_scheduling.attendee_manager import AttendeeManager
from backend.modules.module3_resource_opt.engine import ResourceOptimizer
from backend.modules.module4_participant_xp.recommender import ParticipantExperienceEngine
from backend.modules.module5_comm_agent.agent import CommunicationAgent
from backend.modules.module6_feedback.analyzer import FeedbackAnalyzer
from backend.modules.module7_analytics.generator import EventAnalyticsEngine
from backend.core.safety.kavach import KavachEngine
from eval.benchmark.independent_checker import IndependentDBChecker

def test_module_1():
    brief = "2-day Campus AI Hackathon for 180 students with coding workshops and stage mics"
    parsed = parse_event_brief(brief)
    assert parsed["headcount"] == 180
    assert parsed["event_type"] == "hackathon"
    tasks = get_event_task_board("hackathon")
    assert len(tasks) > 0
    print("[PASS] Module 1: AI Copilot & Adaptive Intake")

def test_module_2():
    rooms = [{"id": "r1", "name": "Audi A", "capacity": 300}, {"id": "r2", "name": "Lab 1", "capacity": 60}]
    slots = ["09:30-11:00", "11:15-12:45"]
    sessions = [
        {"id": "s1", "title": "Opening Keynote", "expected_attendance": 200, "speaker_id": "sp1", "depends_on": None},
        {"id": "s2", "title": "Lab Sprint", "expected_attendance": 50, "speaker_id": "sp2", "depends_on": "s1"}
    ]
    solver = EventScheduler(rooms=rooms, slots=slots, sessions=sessions)
    res = solver.solve()
    assert res["success"] is True
    print("[PASS] Module 2: Intelligent Scheduling (OR-Tools CP-SAT)")

def test_module_3():
    opt = ResourceOptimizer()
    preds = opt.estimate_resources(headcount=150, duration_hours=4.0, event_type="hackathon")
    assert "predicted_needs" in preds
    assert "food_packs" in preds["predicted_needs"]
    recs = opt.get_smart_recommendations("hackathon", 150)
    assert len(recs) > 0
    print("[PASS] Module 3: Resource Optimization (Ridge Regression)")

def test_module_4():
    xp = ParticipantExperienceEngine()
    interests = ["AI/ML", "Python"]
    sessions = [
        {"id": "sess_01", "title": "Generative AI Systems Masterclass", "track": "AI/ML", "slot_time": "10:00 - 11:30"},
        {"id": "sess_02", "title": "Web3 Smart Contracts", "track": "Blockchain", "slot_time": "10:00 - 11:30"}
    ]
    rec = xp.recommend_sessions(interests, sessions, top_k=2)
    assert len(rec) > 0
    assert "Generative AI" in rec[0]["title"]
    print("[PASS] Module 4: Personalized Participant Experience (TF-IDF)")

def test_module_5():
    comm = CommunicationAgent()
    ans = comm.answer_query("ev_001", "What is the venue of the event?")
    assert "answer" in ans
    assert ans["found"] is True
    print("[PASS] Module 5: AI Communication Agent (Grounded Q&A)")

def test_module_6():
    fb = FeedbackAnalyzer()
    res = fb.analyze_sentiment("The keynote was very inspiring and clear!", rating=5)
    assert res["sentiment"] == "positive"
    themes = fb.detect_themes("The lunch boxes and sound system were great")
    assert "hospitality" in themes
    print("[PASS] Module 6: Automated Feedback Intelligence (Sentiment & Themes)")

def test_module_7():
    analytics = EventAnalyticsEngine()
    metrics = analytics.compute_event_metrics("ev_001")
    assert "attendance_rate_percent" in metrics
    report = analytics.generate_executive_report_pdf("ev_001")
    assert os.path.exists(report)
    cert = analytics.generate_certificate(student_name="Student 1", event_name="AI Hackathon", student_id="stud_001", event_id="ev_001", verify_base_url="http://127.0.0.1:8000")
    assert os.path.exists(cert["pdf_path"])
    print("[PASS] Module 7: Post-Event Analytics & Verifiable Certificates (ReportLab + QR)")

def test_safety_and_audit():
    checker = IndependentDBChecker()
    audit = checker.run_full_audit()
    assert audit["audit_passed"] is True
    print("[PASS] Kavach Safety & Raw SQLite Audit: 100% PURE (Zero Overlaps, Zero Leaks)")

if __name__ == "__main__":
    print("=== Testing All 7 SparkX 3.0 Modules End-to-End ===")
    test_module_1()
    test_module_2()
    test_module_3()
    test_module_4()
    test_module_5()
    test_module_6()
    test_module_7()
    test_safety_and_audit()
    print("==================================================")
    print("ALL 7 MODULES FULLY OPERATIONAL & VERIFIED!")
