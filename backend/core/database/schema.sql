-- AgenticLiner SQLite Database Schema
-- Version 2.0 (Academic & Campus Resource Operations)
-- SparkX 3.0 Challenge #1

PRAGMA foreign_keys = ON;

-- 0. Users & Authentication
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('supervisor', 'organiser', 'data_manager', 'participant')),
    full_name TEXT NOT NULL,
    department TEXT DEFAULT 'General',
    is_verified BOOLEAN DEFAULT 1,
    failed_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 0.1 OTP Verifications Table (Signup & Password Reset)
CREATE TABLE IF NOT EXISTS otp_verifications (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    otp_code TEXT NOT NULL,
    purpose TEXT NOT NULL, -- signup, password_reset
    payload_json TEXT, -- json of pending details
    attempts INTEGER DEFAULT 0,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 1. Events Table
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    brief TEXT NOT NULL,
    event_type TEXT DEFAULT 'general', -- hackathon, cultural, workshop, seminar
    expected_participants INTEGER DEFAULT 100,
    organizer_department TEXT DEFAULT 'School of AI',
    approval_status TEXT DEFAULT 'auto_approved', -- auto_approved, pending_dean_approval, approved
    status TEXT DEFAULT 'planned', -- planned, allocated, completed, cancelled
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Rooms / Venues (Campus Infrastructure)
CREATE TABLE IF NOT EXISTS rooms (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    capacity INTEGER NOT NULL,
    location TEXT,
    has_projector BOOLEAN DEFAULT 1,
    has_audio BOOLEAN DEFAULT 1,
    requires_special_approval BOOLEAN DEFAULT 0 -- e.g. Main Audi requires Dean sign-off
);

-- 3. Speakers & Faculty Mentors
CREATE TABLE IF NOT EXISTS speakers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT,
    topics TEXT, -- comma-separated or JSON array
    email TEXT,
    phone TEXT,
    availability_json TEXT
);

-- 4. Resources & Equipment Catalog (Campus Logistics Inventory)
CREATE TABLE IF NOT EXISTS resources (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL, -- venue, equipment, food, volunteers, transport, misc
    name TEXT NOT NULL,
    stock INTEGER NOT NULL DEFAULT 1,
    allocated_stock INTEGER NOT NULL DEFAULT 0,
    unit TEXT DEFAULT 'unit',
    requires_approval BOOLEAN DEFAULT 0,
    description TEXT
);

-- 5. Sessions / Agenda Breakdown
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    title TEXT NOT NULL,
    speaker_id TEXT,
    room_id TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_minutes INTEGER DEFAULT 60,
    expected_attendance INTEGER DEFAULT 50,
    depends_on TEXT, -- prerequisite session_id
    track TEXT DEFAULT 'General',
    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY(room_id) REFERENCES rooms(id),
    FOREIGN KEY(speaker_id) REFERENCES speakers(id)
);

-- 6. Resource Allocations / Bookings (Campus Equipment, Halls & Volunteer Reserves)
CREATE TABLE IF NOT EXISTS bookings (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    resource_id TEXT,
    room_id TEXT,
    item_name TEXT NOT NULL,
    category TEXT NOT NULL,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    quantity INTEGER DEFAULT 1,
    approval_status TEXT DEFAULT 'auto_approved', -- auto_approved, pending_dean_approval, approved
    status TEXT DEFAULT 'confirmed', -- confirmed, rolled_back, cancelled
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
);

-- 7. Students / Attendees (Synthetic Campus Profiles)
CREATE TABLE IF NOT EXISTS students (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    department TEXT NOT NULL,
    year INTEGER NOT NULL,
    interests TEXT -- JSON array of topics
);

-- 8. Event Registrations & Attendee Management
CREATE TABLE IF NOT EXISTS registrations (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'confirmed', -- confirmed, waitlisted, cancelled
    interests_snapshot TEXT,
    preferred_sessions TEXT, -- JSON array of session IDs
    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY(student_id) REFERENCES students(id),
    UNIQUE(event_id, student_id)
);

-- 9. Session Attendance (Live QR Gate Check-in)
CREATE TABLE IF NOT EXISTS attendance (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    checked_in_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    check_in_code TEXT,
    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY(student_id) REFERENCES students(id),
    UNIQUE(session_id, student_id)
);

-- 10. Feedback
CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    student_id TEXT,
    rating INTEGER CHECK(rating BETWEEN 1 AND 5),
    comment TEXT,
    sentiment TEXT, -- positive, neutral, negative
    sentiment_score REAL,
    theme TEXT, -- venue, content, hospitality, organization, general
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
);

-- 11. Outbox (Transactional Messaging Pattern)
CREATE TABLE IF NOT EXISTS outbox (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    type TEXT DEFAULT 'general', -- confirmation, reminder, schedule_change, certificate
    status TEXT DEFAULT 'held', -- held, sent, failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMP,
    error_message TEXT,
    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
);

-- 12. Verifiable Certificates
CREATE TABLE IF NOT EXISTS certificates (
    id TEXT PRIMARY KEY, -- Unique Certificate ID
    student_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    qr_code_path TEXT,
    pdf_path TEXT,
    verified_count INTEGER DEFAULT 0,
    FOREIGN KEY(student_id) REFERENCES students(id),
    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
);

-- 13. Audit Log (Autonomous Actions Tracking)
CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    event_id TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actor TEXT NOT NULL, -- 'user', 'autopilot_agent', 'safety_layer'
    action TEXT NOT NULL, -- tool_call, rollback, savepoint, commit, notice_release
    details_json TEXT,
    result TEXT -- 'SUCCESS', 'FAILED', 'BLOCKED'
);

-- 14. Historical Events for ML Baseline / Training
CREATE TABLE IF NOT EXISTS historical_events (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    event_type TEXT NOT NULL,
    headcount INTEGER NOT NULL,
    duration_hours REAL NOT NULL,
    rooms_needed INTEGER NOT NULL,
    volunteers_needed INTEGER NOT NULL,
    mics_needed INTEGER NOT NULL,
    food_packs_needed INTEGER NOT NULL,
    buses_needed INTEGER DEFAULT 0
);
