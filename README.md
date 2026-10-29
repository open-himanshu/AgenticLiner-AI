# AgenticLiner 🚀
> **AI-Powered Intelligent Event Planning & Management Platform with Built-in Safety Layer & Autopilot Mode**  
> *SparkX 3.0 International Innovation Challenge — Challenge #1*

---

## 📁 Project Architecture & Folder Organization

```
AgenticLiner/
├── backend/
│   ├── api/                              # FastAPI Routers & Pydantic Request/Response contracts
│   ├── core/
│   │   ├── database/                     # SQLite connection, schema definition & migrations
│   │   ├── safety/                       # Kavach: Invariant checker, savepoints, rollback, outbox
│   │   ├── planner/                      # LLM loop, Gemini function calling, Autopilot agent
│   │   └── scheduler/                    # Google OR-Tools CP-SAT conflict-free solver
│   ├── modules/
│   │   ├── module1_coplan/               # M1: Event Planning Copilot (Brief to JSON, Adaptive Intake)
│   │   ├── module2_scheduling/           # M2: Intelligent Scheduling, Flyer & Registration Form
│   │   ├── module3_resource_opt/         # M3: Resource Predictor, Catalog & Budget Optimizer
│   │   ├── module4_participant_xp/       # M4: Personalized Recommendations (TF-IDF Similarity)
│   │   ├── module5_comm_agent/           # M5: AI Communication Agent (Q&A Assistant, Reminders, FAQs)
│   │   ├── module6_feedback/             # M6: Automated Feedback Intelligence (Sentiment & Themes)
│   │   └── module7_analytics/            # M7: Post-Event AI Analytics, Certificates & Executive PDF
│   └── data/
│       └── synthetic/                    # Synthetic generators (past events, venues, inventory, students)
├── frontend/
│   ├── templates/                        # Server-rendered Jinja2 HTML pages (Bootstrap 5)
│   └── static/
│       ├── css/                          # Custom styles (Responsive & clean)
│       ├── js/                           # Vanilla JS for live Autopilot activity panel & cart
│       └── vendor/                       # Local offline assets (Bootstrap, Chart.js)
├── eval/
│   ├── prompts/                          # 50-Prompt test suite (Clean, Ambiguous, Conflict, Destructive)
│   └── benchmark/                        # Independent checker scripts & metrics logger
├── tests/
│   ├── unit/                             # Unit tests for modules and algorithms
│   ├── integration/                      # End-to-end API pipeline tests
│   └── safety/                           # Kavach safety layer, savepoint & invariant tests
├── docs/                                 # API specifications, User Manual & Architectural diagrams
├── .env.example                          # Environment configuration template
├── requirements.txt                      # Project dependencies
└── README.md                             # Project overview and run guide
```

---

## ⚡ Quickstart

1. **Environment Setup:**
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure Environment:**
   ```bash
   cp .env.example .env
   # Add your GEMINI_API_KEY inside .env
   ```

3. **Run Application:**
   ```bash
   python -m uvicorn backend.api.main:app --reload
   ```
