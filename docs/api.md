# AgenticLiner API Contract Specification (v1.0)
> **SparkX 3.0 Innovation Challenge — Challenge #1**

---

## 1. Overview
The AgenticLiner backend exposes both REST API endpoints and interactive server-rendered web interfaces. All mutations are sandboxed and monitored by the **Kavach Safety Engine**.

---

## 2. Core Endpoints

### 2.1 Autopilot Agent Execution
- **Endpoint:** `POST /api/autopilot/run`
- **Description:** Runs the autonomous planning, tool discovery, and booking pipeline with live step logging.
- **Request Body:**
  ```json
  {
    "prompt": "Organize a campus coding hackathon for 150 students with budget 45000",
    "budget": 45000.0,
    "date": "2026-11-25",
    "start_time": "09:00:00",
    "end_time": "17:00:00"
  }
  ```
- **Response:**
  ```json
  {
    "success": true,
    "event_id": "ev_auto_b88b2a12",
    "event_name": "Campus AI Hackathon",
    "venue": "Main Auditorium A (C-Block)",
    "total_cost": 29800.0,
    "timeline": [
      {
        "step": 1,
        "tool": "adaptive_intake",
        "status": "completed",
        "summary": "Extracted: Event Type='Hackathon', Headcount=150, Budget=Rs 45000."
      },
      {
        "step": 4,
        "tool": "book_event_resources",
        "status": "committed",
        "summary": "Kavach Safety checks passed. Booked Main Auditorium A and 3 items."
      }
    ]
  }
  ```

---

### 2.2 Marketplace & Catalog
- **Endpoint:** `GET /api/catalog`
- **Description:** Returns campus resources (venues, equipment, food, volunteers, transport).
- **Response:**
  ```json
  {
    "catalog": [
      {
        "id": "res_mic_cordless",
        "category": "equipment",
        "name": "Wireless Handheld Mic Set (Pair)",
        "price": 400.0,
        "stock": 10,
        "unit": "pair"
      }
    ]
  }
  ```

---

### 2.3 Intelligent Timetable Constraint Solver (OR-Tools)
- **Endpoint:** `POST /api/schedule/solve`
- **Description:** Formulates and solves room conflict, speaker availability, and dependency constraints using Google OR-Tools CP-SAT.
- **Response:**
  ```json
  {
    "success": true,
    "status": "OPTIMAL",
    "total_sessions_scheduled": 4,
    "schedule": [
      {
        "session_id": "sess_01",
        "session_title": "Opening Keynote & Welcome",
        "room_name": "Main Auditorium A (C-Block)",
        "slot_time": "09:30-11:00"
      }
    ]
  }
  ```

---

### 2.4 Personalized Participant Recommendations
- **Endpoint:** `GET /api/participant/{student_id}/recommendations`
- **Description:** Calculates TF-IDF interest vector cosine similarities and filters clashing slots.

---

### 2.5 Grounded Event Assistant
- **Endpoint:** `POST /api/assistant/ask`
- **Description:** Q&A engine grounded in official schedule and venue records (zero hallucination).

---

### 2.6 Feedback Intelligence
- **Endpoint:** `POST /api/feedback/submit`
- **Description:** Sentiment polarity scoring and thematic classification (Venue, Content, Hospitality, Organization).

---

### 2.7 Online Certificate Verification
- **Endpoint:** `GET /verify/{cert_id}`
- **Description:** Public verification page scanned via dynamic QR code.
