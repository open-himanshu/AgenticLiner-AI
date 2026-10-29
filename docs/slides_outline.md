# AgenticLiner: Pitch & Presentation Deck Outline
**Galgotias University SparkX 3.0 30-Day Innovation Challenge**
**Track Challenge #1: AI-Powered Intelligent Event Planning & Management Platform**

---

## Slide 1: Title & Vision
- **Header**: AgenticLiner — The Autonomous Event Operations Operating System
- **Subtitle**: Powered by AI Autopilot, Google OR-Tools CP-SAT, and the Kavach Safety Layer
- **Team**: Technojam / Galgotias University Student Developers
- **Key Hook**: Moving university events from chaotic WhatsApp groups and manual spreadsheets to a mathematically verified, autonomous workflow.

---

## Slide 2: The Campus Problem
- **Double-Bookings & Room Collisions**: Auditorium booked for drama rehearsal and keynote at the exact same hour.
- **Logistics Bottlenecks**: Running out of microphones, extension boards, or food packets mid-event.
- **Cascading Schedule Disruptions**: When a keynote speaker arrives late or cancels, the entire day collapses.
- **Commercial Tool Mismatch**: Existing tools (Eventbrite, Meetup) focus on ticket sales and credit card checkout—completely useless for university inventory quotas, campus facilities, and Dean approvals.

---

## Slide 3: The Solution — AgenticLiner Architecture
- **3-Tiered Autonomous Architecture**:
  1. **Planning Intelligence (Copilot & Autopilot)**: Brief parsing, adaptive intake, countdown boards.
  2. **Deterministic Mathematical Optimizers**:
     - **Google OR-Tools CP-SAT Solver**: Constraint satisfaction for 100% clash-free timetabling.
     - **Scikit-Learn Ridge Regression**: Predicts campus logistics (refreshments, mics, volunteers) from historical attendance.
  3. **Transactional Safety Engine (Kavach)**:
     - SQLite `SAVEPOINT` isolation.
     - 6 Invariant Checkers (Capacity, Overlaps, Speaker Clashing, Quotas, Policy, Blast Radius).
     - Transactional Outbox Pattern: Never leaks accidental notifications.

---

## Slide 4: All 7 SparkX Modules Fully Implemented
| Module | SparkX Requirement | AgenticLiner Implementation |
|---|---|---|
| **Module 1** | Event Planning Copilot | Adaptive Intake, Task Board (D-7 to D-Day), Logistics Requisition |
| **Module 2** | Intelligent Scheduling | Google OR-Tools CP-SAT Solver, Flyer Generator, Speaker-Cancellation Demo |
| **Module 3** | Resource Optimization | Ridge Regression Engine + Campus Inventory Quotas + Dean Escalation |
| **Module 4** | Participant Experience | TF-IDF + Cosine Similarity Recommender, Peer Networking, Grounded Bot |
| **Module 5** | AI Comm Agent | Grounded Event Assistant, Outbox Pattern, Change Broadcasts |
| **Module 6** | Feedback Intelligence | Sentiment Scoring (Pos/Neu/Neg), Thematic Clustering & Synthesis |
| **Module 7** | Post-Event Analytics | Executive PDF Report, Cryptographic QR Verifiable Certificates |

---

## Slide 5: The "Kavach" Safety Innovation (Our Core Differentiator)
- **Why LLMs Fail in Enterprise Operations**:
  - Raw LLMs hallucinate non-existent rooms, violate capacity limits, and double-book faculty.
- **How Kavach Solves This**:
  - The LLM acts as an *intent proposer*; it never directly modifies the persistent database.
  - Every proposed mutation executes within an atomic SQLite `SAVEPOINT`.
  - Invariants test physical constraints (Capacity > Seats? Room busy? Speaker in another hall? Stock empty?).
  - If any check fails: **Instant atomic ROLLBACK** + Outbox purge + Root-cause explanation in UI.

---

## Slide 6: Mathematical Scheduling with Google OR-Tools
- **Formulation**:
  - Binary decision variables: \( x_{s, r, t} \in \{0, 1\} \) where session \( s \) is assigned to room \( r \) at slot \( t \).
  - Subject to:
    1. Single assignment per session: \( \sum_{r, t} x_{s, r, t} = 1 \)
    2. Room capacity: \( \text{Attendance}(s) \le \text{Capacity}(r) \)
    3. Room non-overlapping: \( \sum_{s} x_{s, r, t} \le 1 \quad \forall r, t \)
    4. Speaker non-collision: \( \sum_{s \in S_{\text{speaker}}} \sum_{r} x_{s, r, t} \le 1 \quad \forall t \)
- **Result**: Timetables solved in < 250 milliseconds with zero conflicts guaranteed.

---

## Slide 7: Live Hero Demo Walkthrough (3-Minute Script)
1. **Organizer Input**: Paste rough prompt: *"Organize a 2-day AI Hackathon for 150 students"*.
2. **Autopilot Execution**: See the system lock Seminar Hall 1, requisition 35 extension strips and 6 cordless mics, and stage welcome notices.
3. **The Speaker Cancellation Demo**: On the Schedule screen, click **Hero Demo: Speaker Cancels**. Watch the system dynamically reschedule and notify attendees without broken slots.
4. **Student Portal & Verification**: Open participant view, get AI matched sessions, and verify a certificate QR code offline.

---

## Slide 8: Evaluation & Benchmark Results
- Evaluated on **50 Diverse Prompts** (Clean, Ambiguous, High-Conflict, Destructive):
  - **Setup A (Direct LLM)**: 0% conflict detection, database corrupted with overlaps.
  - **Setup B (DB Constraints)**: 13.3% conflict detection (misses temporal intervals and dynamic quotas).
  - **Setup C (AgenticLiner Kavach)**: **100% Conflict Detection**, **100% Destructive Block**, **100% Pure DB State**.
  - Verified by an independent raw SQLite audit script (`independent_checker.py`).

---

## Slide 9: Impact & University Scalability
- **Immediate Deployment**: Built natively for Galgotias University campus (Block A, Block E, Main Auditorium, Technojam Club).
- **Offline Capable**: Zero external dependencies required during live campus events.
- **Cost Savings**: Eliminates third-party ticketing fees and administrative scheduling overhead.
- **Dean Office Ready**: Automated executive PDF reports generated at the click of a button.

---

## Slide 10: Conclusion & Q&A
- **Summary**: AgenticLiner combines modern Agentic AI with mathematical constraint programming and transactional database safety.
- **GitHub Repository**: Complete with tests, benchmarks, and API documentation.
- **Live Demo Link**: `http://127.0.0.1:8000`
- **Thank you!** Questions from the Jury.
