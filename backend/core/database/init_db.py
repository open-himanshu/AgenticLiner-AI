"""
Database Initializer and Campus Seed Data Generator for AgenticLiner.
Sets up the SQLite database and populates realistic Galgotias University campus resources.
Academic operations: no commercial prices or wallets. Pure campus logistics & permissions.
"""
import sqlite3
import json
import os
import sys
from pathlib import Path

# Ensure root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from backend.core.database.connection import get_connection, get_db_path

SCHEMA_FILE = Path(__file__).parent / "schema.sql"

def init_database(db_conn: sqlite3.Connection = None):
    conn = db_conn or get_connection()
    try:
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)
        print("Database schema initialized successfully.")
    finally:
        if not db_conn:
            conn.close()

def seed_campus_data(db_conn: sqlite3.Connection = None, force_reseed: bool = False):
    conn = db_conn or get_connection()
    try:
        cursor = conn.cursor()

        if not force_reseed:
            cursor.execute("SELECT count(*) as count FROM rooms")
            if cursor.fetchone()[0] > 0:
                print("Campus data already seeded. Skipping.")
                return

        print("Seeding Galgotias University campus venues & inventory...")

        # Clear existing tables if force reseed
        cursor.execute("PRAGMA foreign_keys = OFF;")
        tables = [
            "certificates", "feedback", "attendance", "registrations", 
            "bookings", "sessions", "rooms", "speakers", "resources", 
            "students", "historical_events", "events", "outbox", "audit_log"
        ]
        for t in tables:
            cursor.execute(f"DELETE FROM {t}")
        cursor.execute("PRAGMA foreign_keys = ON;")

        # 1. Rooms / Venues (Academic Facilities)
        rooms = [
            ("room_audi_a", "Main Auditorium A (C-Block)", 500, "Block C, Ground Floor", 1, 1, 1), # requires Dean approval
            ("room_audi_b", "Auditorium B (Mini Hall)", 220, "Block B, 2nd Floor", 1, 1, 0),
            ("room_sem_101", "Seminar Hall 1", 120, "Block A, 1st Floor", 1, 1, 0),
            ("room_sem_102", "Seminar Hall 2", 90, "Block A, 1st Floor", 1, 1, 0),
            ("room_ai_lab", "AI & Data Science Specialized Lab", 65, "Block E, 3rd Floor", 1, 1, 0),
            ("room_comp_lab", "Advanced Computing Lab 4", 45, "Block E, 2nd Floor", 1, 0, 0),
            ("room_conf_room", "Executive Conference Room", 30, "Admin Block, 4th Floor", 1, 1, 0),
        ]
        cursor.executemany(
            "INSERT INTO rooms (id, name, capacity, location, has_projector, has_audio, requires_special_approval) VALUES (?, ?, ?, ?, ?, ?, ?)",
            rooms
        )

        # 2. Speakers & Faculty Mentors
        speakers = [
            ("spk_01", "Dr. Vartika Puri", "School of AI", "Generative AI, AI Safety, Optimization", "vartika.puri@galgotiasuniversity.edu.in", "+919560430101", json.dumps(["09:00-13:00", "14:00-17:00"])),
            ("spk_02", "Prof. Akhilesh Sir", "Machine Learning Group", "Machine Learning, Deep Learning, MLOps", "akhilesh.ml@galgotiasuniversity.edu.in", "+919876543210", json.dumps(["10:00-16:00"])),
            ("spk_03", "Prof. Niraj Sir", "Python for AI", "Algorithms, Python Architecture, Data Pipelines", "niraj.ai@galgotiasuniversity.edu.in", "+919811223344", json.dumps(["11:00-15:00", "16:00-18:00"])),
            ("spk_04", "Dr. Manish Raj", "Dean SoAI", "Keynotes, Industry AI, Future Tech", "dean.soai@galgotiasuniversity.edu.in", "+919877112233", json.dumps(["09:30-11:30"])),
            ("spk_05", "Dr. Neha Verma (Substitute)", "School of AI", "Machine Learning, Generative AI, Data Science", "neha.ai@galgotiasuniversity.edu.in", "+919876112233", json.dumps(["09:00-17:00"])),
        ]
        cursor.executemany(
            "INSERT INTO speakers (id, name, department, topics, email, phone, availability_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            speakers
        )

        # 3. Campus Logistics & Resource Inventory (Stock, units, approval tiers)
        catalog = [
            ("res_mic_cordless", "equipment", "Wireless Handheld Mic Set (Pair)", 12, 0, "pair", 0, "Dual wireless UHF cordless mics"),
            ("res_mic_collar", "equipment", "Lapel / Collar Mic (Wireless)", 8, 0, "unit", 0, "Crisp presenter collar microphone"),
            ("res_sound_jbl", "equipment", "JBL High-Power Sound & PA System", 4, 0, "set", 0, "Heavy audio setup with digital mixer"),
            ("res_led_lights", "equipment", "Stage LED Par Lights & Spotlights", 6, 0, "set", 0, "Multi-color stage lighting setup"),
            ("res_projector_4k", "equipment", "Ultra HD 4K Laser Projector", 5, 0, "unit", 0, "High lumens projector for day/night halls"),
            ("res_ext_boards", "equipment", "Heavy Duty Extension Spike Boards", 35, 0, "unit", 0, "Multi-socket power strips for laptops"),
            ("res_food_snack", "food", "Standard Refreshment Snack Box", 1500, 0, "box", 0, "Juice, samosa, sandwich, and cookie"),
            ("res_food_lunch", "food", "Campus Special Lunch Box / Buffet", 1000, 0, "pack", 0, "Nutritious campus meal for students and faculty"),
            ("res_volunteer_reg", "volunteers", "Student Volunteers (Registration & Helpdesk)", 30, 0, "person", 0, "Trained student coordinators"),
            ("res_volunteer_stage", "volunteers", "Stage & Speaker Volunteer Coordinators", 20, 0, "person", 0, "Stage hands and mic managers"),
            ("res_first_aid", "misc", "Campus Emergency Medical Kit", 10, 0, "kit", 0, "First aid and emergency assistance supplies"),
            ("res_banner_standee", "misc", "Campus Roll-up Standees & Podium Banner", 8, 0, "set", 0, "Official Galgotias branded banners"),
            ("res_bus_shuttle", "transport", "University Shuttle Bus (50 Seater)", 4, 0, "bus", 1, "Campus shuttle between metro/gates and hall (Requires Dean approval)"),
        ]
        cursor.executemany(
            "INSERT INTO resources (id, category, name, stock, allocated_stock, unit, requires_approval, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            catalog
        )

        # 4. Synthetic Students (50 Profiles)
        departments = ["B.Tech AIML", "B.Tech CSE", "B.Tech Data Science", "B.Tech Cyber Security", "BCA", "MCA"]
        interest_pools = [
            ["AI/ML", "Deep Learning", "Generative AI", "Hackathons"],
            ["Web Development", "React", "Cloud Computing", "UI/UX"],
            ["Robotics", "IoT", "Embedded Systems", "Hardware"],
            ["Cybersecurity", "Ethical Hacking", "Networks", "CTF"],
            ["Competitive Programming", "Algorithms", "DSA", "Open Source"]
        ]
        
        student_records = []
        for i in range(1, 51):
            dept = departments[i % len(departments)]
            interests = interest_pools[i % len(interest_pools)]
            student_records.append((
                f"stud_{i:03d}",
                f"Student {i}",
                f"student{i}@galgotiasuniversity.edu.in",
                dept,
                (i % 4) + 1,
                json.dumps(interests)
            ))
        cursor.executemany(
            "INSERT INTO students (id, name, email, department, year, interests) VALUES (?, ?, ?, ?, ?, ?)",
            student_records
        )

        # 5. Historical Events for ML Baseline (10 events)
        history_events = [
            ("hist_01", "Technojam Hackathon 2024", "hackathon", 180, 24.0, 3, 14, 6, 200, 0),
            ("hist_02", "Annual Cultural Fest Solo Dance", "cultural", 250, 4.0, 1, 10, 8, 260, 1),
            ("hist_03", "AI Workshop: Hands-on PyTorch", "workshop", 85, 5.0, 1, 4, 3, 95, 0),
            ("hist_04", "Cyber Security Capture The Flag", "hackathon", 120, 12.0, 2, 8, 4, 130, 0),
            ("hist_05", "National Science Day Seminar", "seminar", 300, 6.0, 1, 12, 6, 320, 2),
            ("hist_06", "Web3 Developer Bootcamp", "workshop", 60, 4.0, 1, 3, 2, 65, 0),
            ("hist_07", "Inter-College Debate Championship", "cultural", 110, 5.0, 1, 6, 4, 120, 0),
            ("hist_08", "RoboWars Arena League", "hackathon", 150, 8.0, 2, 12, 4, 160, 0),
            ("hist_09", "Cloud Computing Summit", "seminar", 200, 7.0, 1, 10, 5, 210, 1),
            ("hist_10", "Alumni Networking Gala", "seminar", 160, 4.0, 1, 8, 4, 180, 1),
        ]
        cursor.executemany(
            "INSERT INTO historical_events (id, title, event_type, headcount, duration_hours, rooms_needed, volunteers_needed, mics_needed, food_packs_needed, buses_needed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            history_events
        )

        # 6. Default Active Campus Event (ev_001)
        cursor.execute("""
            INSERT OR IGNORE INTO events (id, name, brief, event_type, expected_participants, organizer_department, status)
            VALUES ('ev_001', 'Galgotias Campus Innovation Hackathon 2026', '2-day campus hackathon on Generative AI and Autonomous Agents', 'hackathon', 180, 'School of AI', 'allocated')
        """)

        # Default Sessions for ev_001
        default_sessions = [
            ("sess_01", "ev_001", "Opening Keynote & Welcome", "spk_04", "room_audi_a", "2026-11-25 09:30:00", "2026-11-25 11:00:00", 90, 250, None, "Keynote"),
            ("sess_02", "ev_001", "Generative AI Systems Masterclass", "spk_01", "room_audi_b", "2026-11-25 11:15:00", "2026-11-25 12:45:00", 90, 120, "sess_01", "AI/ML"),
            ("sess_03", "ev_001", "Deep Learning with PyTorch Workshop", "spk_02", "room_ai_lab", "2026-11-25 13:45:00", "2026-11-25 15:15:00", 90, 50, "sess_02", "AI/ML"),
            ("sess_04", "ev_001", "Python for Autonomous Agents", "spk_03", "room_sem_101", "2026-11-25 15:30:00", "2026-11-25 17:00:00", 90, 80, "sess_01", "Software"),
        ]
        cursor.executemany("""
            INSERT OR IGNORE INTO sessions (id, event_id, title, speaker_id, room_id, start_time, end_time, duration_minutes, expected_attendance, depends_on, track)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, default_sessions)

        # Default Bookings for ev_001
        default_bookings = [
            ("bk_01", "ev_001", None, "room_audi_a", "Main Auditorium A", "venue", "2026-11-25 09:00:00", "2026-11-25 17:00:00", 1, "confirmed"),
            ("bk_02", "ev_001", None, "room_audi_b", "Auditorium B", "venue", "2026-11-25 11:00:00", "2026-11-25 13:00:00", 1, "confirmed"),
            ("bk_03", "ev_001", None, "room_ai_lab", "AI Specialized Lab", "venue", "2026-11-25 13:30:00", "2026-11-25 15:30:00", 1, "confirmed"),
            ("bk_04", "ev_001", None, "room_sem_101", "Seminar Hall 1", "venue", "2026-11-25 15:00:00", "2026-11-25 17:00:00", 1, "confirmed"),
        ]
        cursor.executemany("""
            INSERT OR IGNORE INTO bookings (id, event_id, resource_id, room_id, item_name, category, start_time, end_time, quantity, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, default_bookings)

        conn.commit()
        print("Academic campus seed data committed successfully.")
    finally:
        if not db_conn:
            conn.close()

if __name__ == "__main__":
    init_database()
    seed_campus_data(force_reseed=True)
