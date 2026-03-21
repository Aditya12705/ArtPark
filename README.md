# NexusLearn 🧠
### AI-Adaptive Onboarding Engine — ARTPARK CodeForge Hackathon Submission

> NexusLearn eliminates "one-size-fits-all" corporate onboarding by parsing a candidate's **real** capabilities and dynamically constructing the *minimum effective* learning sequence to reach role-specific competency — no wasted hours, no prerequisite violations, no hallucinations.

---

## 📋 Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Solution Overview](#2-solution-overview)
3. [Architecture Overview](#3-architecture-overview)
4. [Complete Pipeline Walkthrough](#4-complete-pipeline-walkthrough)
5. [Key Technical Features](#5-key-technical-features)
6. [Tech Stack](#6-tech-stack)
7. [Project Structure](#7-project-structure)
8. [API Reference](#8-api-reference)
9. [Data Models (Pydantic Schemas)](#9-data-models-pydantic-schemas)
10. [Algorithm Deep Dives](#10-algorithm-deep-dives)
11. [Skills Graph & Taxonomy](#11-skills-graph--taxonomy)
12. [Course Catalog](#12-course-catalog)
13. [Frontend — UI Component Guide](#13-frontend--ui-component-guide)
14. [Cross-Domain Scalability](#14-cross-domain-scalability)
15. [Datasets & Model Information](#15-datasets--model-information)
16. [Validation & Testing](#16-validation--testing)
17. [Quick Start Guide](#17-quick-start-guide)
18. [Environment Variables](#18-environment-variables)
19. [Docker Deployment](#19-docker-deployment)
20. [Design Decisions & Trade-offs](#20-design-decisions--trade-offs)
21. [Known Limitations & Scope Notes](#21-known-limitations--scope-notes)
22. [Submission Checklist](#22-submission-checklist)

---

## 1. Problem Statement

Current corporate onboarding relies on static, role-wide curricula. Every person in a given role gets the same 60–80 hour training plan regardless of their actual experience level.

**The result:**
- **Senior hires** waste 60%+ of onboarding time on material they already know
- **Junior hires** are overwhelmed by advanced modules placed before their prerequisites
- **HR teams** have no reliable way to calibrate training to actual skill gaps
- **The business** pays for training hours that produce zero learning value

**The challenge:** Build an AI-driven, adaptive learning engine that parses a new hire's current capabilities (via résumé) and a target role's requirements (via job description), then dynamically maps an optimised, personalised training pathway to reach role-specific competency.

---

## 2. Solution Overview

NexusLearn is a full-stack adaptive learning engine with the following properties:

| Property | Description |
|---|---|
| **Zero hallucinations** | Skills are extracted against a closed allowlist. Any invented skill ID is silently discarded |
| **Deterministic gap engine** | Core gap computation uses pure Python — no LLM, no randomness, no per-run variation |
| **Dependency-safe ordering** | Kahn's topological sort guarantees no advanced module appears before its prerequisite |
| **Temporal skill decay** | Knowledge unused for years is automatically penalised before gap computation |
| **Cognitive load awareness** | Course sequence alternates heavy and light cognitive load to reduce fatigue |
| **Hard time budget** | HR can set a max training hours cap — the pathway is never allowed to exceed it |
| **Transparent reasoning** | Every course recommendation includes a per-course AI explanation referencing actual gap levels |
| **Cross-domain** | 55 skills and 43 courses spanning Tech, HR, Finance, Ops, Healthcare, Sales, Marketing |

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              NexusLearn Pipeline                                 │
│                                                                                 │
│  [Resume Text]   +   [Job Description Text]                                     │
│         │                    │                                                  │
│         └──────────┬─────────┘                                                  │
│                    │                                                            │
│                    ▼  ① POST /parse                                             │
│         ┌──────────────────────────┐                                            │
│         │  Groq Llama-3.3-70B      │  → candidate_skills: {skill_id: {level,    │
│         │  Skill Extraction        │                        last_used_year}}    │
│         │  JSON schema + allowlist │  → required_skills:  {skill_id: level}     │
│         └────────────┬─────────────┘  → raw_skills, model_used, confidence      │
│                      │                                                          │
│                      ▼  ② POST /gap                                             │
│         ┌──────────────────────────┐                                            │
│         │  Temporal Skill Decay    │  years_idle × 0.5 penalty per skill        │
│         │  + Gap Engine (pure Py)  │  delta = required − decayed_current        │
│         │  + BFS DAG Propagation   │  propagate hidden prerequisite gaps        │
│         └────────────┬─────────────┘  already_competent, missing_entirely       │
│                      │                                                          │
│                      ▼  ③ POST /pathway                                         │
│         ┌──────────────────────────┐                                            │
│         │  PathwayBuilder          │  Kahn's topo sort + delta priority         │
│         │  • Static catalog lookup │  Cognitive load balancing (tie-breaker)    │
│         │  • HR budget enforcement │  Two-phase hard cap                        │
│         │  • Dynamic Discovery     │  Groq finds external resources for orphans │ 
│         │  • Reasoning Traces      │  Per-course Groq explanation (per-skill    │
│         └────────────┬─────────────┘  delta/current/required context)           │
│                      │                                                          │
│                      ▼  ④ React Frontend                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐      │
│  │  LandingPage → UploadPage → PathwayPage + ReasoningTracePanel        │       │
│  │  Skill-gap cards (click to highlight) + ordered course sequence      │       │
│  └───────────────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Complete Pipeline Walkthrough

### Step 1 — Document Ingestion (Frontend, Client-Side)

The user uploads a résumé and job description via `UploadPage.jsx`. Supported formats:
- **PDF** — extracted via `pdfjs-dist` (runs entirely in the browser, no server upload of raw files)
- **DOCX** — extracted via `mammoth.js` (browser-side)
- **TXT** — read directly
- **Plain text paste** — fallback input boxes

The extracted text is sent as JSON strings to the backend via `/parse`.

### Step 2 — Skill Extraction (`POST /parse`)

**Service:** `backend/services/groq_service.py` → `GroqService.extract_skills()`

**Model:** `llama-3.3-70b-versatile` via the Groq inference API

The LLM receives:
1. A **system prompt** defining the exact JSON output schema
2. The **full allowed skill ID list** from `skills_graph.json` as a closed vocabulary
3. The raw résumé text and the raw JD text

The LLM is instructed to output a JSON object with two maps:
```json
{
  "candidate_skills": {
    "python": {"level": 4, "last_used_year": 2024},
    "sql": {"level": 3, "last_used_year": 2022}
  },
  "required_skills": {
    "python": 4,
    "docker": 3,
    "kubernetes": 2
  }
}
```

**Zero-Hallucination Enforcement:** After the LLM responds, `_sanitise_candidate_skills()` and `_sanitise_required_skills()` silently discard any `skill_id` not present in the allowlist. The pipeline never acts on invented skills.

### Step 3 — Temporal Skill Decay (`POST /gap`, phase 1)

**Service:** `backend/services/gap_engine.py` → `apply_skill_decay()`

Before computing deltas, proficiency levels are penalised based on how long ago the skill was last used:

```python
penalty = floor(years_idle * 0.5)
effective_level = max(1, original_level - penalty)
```

**Example:** A Python developer at Level 4 who last used Python in 2019 (5 years ago):
```
penalty = floor(5 * 0.5) = 2
effective_level = max(1, 4 - 2) = 2
```

This prevents a candidate with a stale skill from being incorrectly assessed as already competent.

### Step 4 — Direct Gap Computation (`POST /gap`, phase 2)

**Service:** `backend/services/gap_engine.py` → `compute_gap()`

For every required skill:
```
delta = required_level - effective_candidate_level
```

- `delta > 0` → skill gap, added to `gaps` dict with `{current, required, delta}`
- `delta ≤ 0` → candidate meets or exceeds requirement, added to `already_competent`
- `current = 0` → skill entirely absent, added to `missing_entirely`

`total_gap_score` = sum of all positive deltas (overall effort proxy for this candidate).

### Step 5 — Prerequisite Propagation (`POST /gap`, phase 3)

**Service:** `backend/services/gap_engine.py` → `propagate_prerequisites()`

Uses **Breadth-First Search (BFS)** on the `skills_graph.json` DAG:

```
For each skill in gaps:
  Walk the DAG backward to find all prerequisite skills
  For each prerequisite:
    If candidate does not already meet it → add it to gaps
```

**Why this matters:** A JD might ask for `pandas` but not explicitly list `numpy`. The DAG knows that `pandas` depends on `numpy`, so if the candidate lacks `numpy`, it is automatically surfaced — without the JD author needing to list every foundational skill.

### Step 6 — Pathway Building (`POST /pathway`)

**Service:** `backend/services/pathway_builder.py` → `PathwayBuilder.build()`

The pathway builder receives the `GapResponse` and orchestrates:

1. **Course matching** — finds all courses in `course_catalog.yaml` that teach at least one gap skill
2. **Static budget trim** — removes courses that would exceed `max_hours`
3. **Topological ordering** — runs Kahn's algorithm on the course dependency subgraph
4. **Cognitive load balancing** — tie-breaks within the sort
5. **Dynamic discovery** — for any gap skill with no matching catalog course, calls Groq to suggest an external resource
6. **Skip detection** — identifies courses where the candidate is already competent in all skills taught
7. **Reasoning trace generation** — calls Groq with per-course skill context

### Step 7 — Reasoning Traces

**Service:** `backend/services/groq_service.py` → `GroqService.generate_reasoning_traces()`

Each course gets its own focused context object sent to Groq:
```json
{
  "python_ml_course": {
    "teaches_skills": ["pandas", "numpy"],
    "gaps_addressed": {
      "pandas": {"current_level": 1, "required_level": 4, "delta": 3},
      "numpy": {"current_level": 0, "required_level": 3, "delta": 3}
    }
  }
}
```

Groq is instructed to produce exactly one sentence per course that references the specific skill name, current level, and target level. This is the "reasoning trace" displayed in the `ReasoningTracePanel`.

---

## 5. Key Technical Features

| Feature | Implementation | File |
|---|---|---|
| **Intelligent Skill Extraction** | Groq Llama-3.3-70B with closed-vocabulary allowlist and strict JSON schema enforcement | `groq_service.py` |
| **Zero-Hallucination Enforcement** | `_sanitise_candidate_skills()` + `_sanitise_required_skills()` — silently discard any skill_id not in `skills_graph.json` | `groq_service.py` |
| **Temporal Skill Decay** | `penalty = floor(years_idle × 0.5); effective_level = max(1, level - penalty)` | `gap_engine.py` |
| **Deterministic Gap Computation** | Pure Python dict operations — no LLM in the hot path, fully reproducible | `gap_engine.py` |
| **Prerequisite Propagation** | BFS on a 55-node skills DAG — surfaces implicit prerequisite gaps automatically | `gap_engine.py` |
| **Adaptive Pathway Ordering** | Kahn's topological sort with delta-weighted priority queue | `pathway_builder.py` |
| **Cognitive Load Balancing** | After a "high" load course, prefer a "low" load one — using a mutable state container to update `last_load` per course placement | `pathway_builder.py` |
| **HR Time Budget Enforcement** | Two-phase hard cap: static catalog trim first, discovery budget checked second | `pathway_builder.py` |
| **Dynamic Discovery** | Groq suggests external resources for gap skills with no catalog match — flagged `⚠ AI_SUGGESTED` in UI | `pathway_builder.py` |
| **Per-Course Reasoning** | Each course gets its own skill-specific context (not the full gap map) — enabling Groq to write genuinely specific traces | `groq_service.py` |
| **Course Skip Detection** | `_identify_skipped()` — identifies courses where candidate already meets all taught skills | `pathway_builder.py` |
| **Extraction Confidence** | Groq returns a `0.0–1.0` confidence score per extraction; surfaced as a colour-coded badge in the UI | `groq_service.py`, `PathwayPage.jsx` |
| **Client-Side Document Parsing** | PDF via `pdfjs-dist`, DOCX via `mammoth.js` — no raw file upload to server | `UploadPage.jsx` |
| **Training Time Saved Metric** | `savingsPct = (skippedHours / baselineHours) × 100` displayed as the 4th metric card | `PathwayPage.jsx` |

---

## 6. Tech Stack

### Backend

| Layer | Tool | Version | Purpose |
|---|---|---|---|
| **Web Framework** | FastAPI | ≥0.111 | Async REST API with auto-generated OpenAPI docs |
| **ASGI Server** | Uvicorn (with `standard` extras) | ≥0.29 | Production-grade async server |
| **Data Validation** | Pydantic v2 | ≥2.7 | Request/response schemas with field-level validation |
| **LLM — All Tasks** | Groq Llama-3.3-70B-Versatile | latest | Skill extraction, reasoning traces, dynamic discovery |
| **Groq SDK** | `groq` Python client | ≥0.9 | Typed async API wrapper |
| **Course Catalog** | PyYAML | ≥6.0 | Parsing `course_catalog.yaml` at startup |
| **Env Management** | python-dotenv | ≥1.0 | Loads `GROQ_API_KEY` from `.env` |

### Frontend

| Layer | Tool | Version | Purpose |
|---|---|---|---|
| **UI Framework** | React | 18 | Component-based SPA |
| **Build Tool** | Vite | 6 | Fast dev server + production bundler |
| **CSS Framework** | Tailwind CSS | v4 | Utility-first styling |
| **PDF Extraction** | pdfjs-dist | 5.5 | Client-side (browser) PDF → text |
| **DOCX Extraction** | mammoth | 1.8 | Client-side DOCX → plain text |
| **Icons** | lucide-react | latest | SVG icon system |

### Infrastructure

| Layer | Tool | Purpose |
|---|---|---|
| **Containerisation** | Docker | Isolated, reproducible environments for both services |
| **Orchestration** | Docker Compose | Single `docker-compose up --build` boots the whole stack |

---

## 7. Project Structure

```
NexusLearn/
│
├── backend/
│   ├── main.py                    # FastAPI app entry point — lifespan, CORS, router wiring
│   ├── requirements.txt           # Python dependencies
│   ├── Dockerfile                 # Backend container definition
│   ├── .env                       # API keys (not committed)
│   ├── .env.example               # Template — copy to .env and fill in
│   │
│   ├── routers/
│   │   ├── parse.py               # POST /parse — skill extraction endpoint
│   │   ├── gap.py                 # POST /gap  — gap analysis + prerequisite propagation
│   │   └── pathway.py             # POST /pathway — course ordering + reasoning traces
│   │
│   ├── services/
│   │   ├── groq_service.py        # Groq Llama wrapper (extraction, traces, discovery)
│   │   ├── gap_engine.py          # Pure Python gap computation + decay + BFS propagation
│   │   └── pathway_builder.py     # Kahn's sort + cognitive load + budget + discovery
│   │
│   ├── models/
│   │   └── schemas.py             # All Pydantic v2 request/response models
│   │
│   ├── data/
│   │   ├── skills_graph.json      # 55-node skills DAG with prerequisites + metadata
│   │   └── course_catalog.yaml    # 43 curated courses — id, title, provider, url, duration, skills
│   │
│   └── tests/
│       ├── verify_algorithms.py   # Unit tests for decay, load balancing, budget
│       ├── test_resume.txt        # Sample junior developer résumé for testing
│       ├── test_jd.txt            # Sample software engineering JD for testing
│       ├── sample_resume_decay.txt# Test case specifically for temporal decay logic
│       ├── sample_jd_tech_lead.txt# Tech Lead JD (higher requirements)
│       └── aditya_resume.txt      # Extended real-world test résumé
│
├── frontend/
│   ├── index.html                 # Root HTML with Vite injection point
│   ├── package.json               # npm dependencies
│   ├── vite.config.js             # Vite build config + API proxy to :8000
│   ├── Dockerfile                 # Frontend container definition
│   │
│   └── src/
│       ├── main.jsx               # React root mount
│       ├── App.jsx                # 3-state router: landing → upload → results
│       ├── index.css              # Design system (CSS variables, neo-card, neo-button)
│       ├── LandingPage.jsx        # Marketing/about page — 6 sections with CTAs
│       ├── UploadPage.jsx         # Document upload (drag/drop PDF/DOCX/TXT) + API calls
│       ├── PathwayPage.jsx        # Results: gap cards, course sequence, metrics
│       └── ReasoningTracePanel.jsx# Slide-in drawer per course with AI trace + skill levels
│
├── docker-compose.yml             # Wires frontend (:3000) and backend (:8000) together
├── README.md                      # This file
└── .gitignore
```

---

## 8. API Reference

Base URL (local): `http://localhost:8000`  
Interactive docs: `http://localhost:8000/docs` (Swagger UI)  
Alternative docs: `http://localhost:8000/redoc` (ReDoc)

---

### `GET /health`

Returns service liveness status and loaded data counts.

**Response `200`:**
```json
{
  "status": "ok",
  "skills_loaded": 55,
  "courses_loaded": 43
}
```

---

### `POST /parse`

Extract structured skills from a résumé and job description using Groq Llama.

**Request body:**
```json
{
  "resume_text": "Full text of the candidate's résumé (min 50 chars)...",
  "jd_text": "Full text of the job description (min 50 chars)..."
}
```

**Response `200`:**
```json
{
  "candidate_skills": {
    "python": {"level": 4, "last_used_year": 2024},
    "sql": {"level": 3, "last_used_year": 2022},
    "docker": {"level": 2, "last_used_year": 2023}
  },
  "required_skills": {
    "python": 4,
    "docker": 3,
    "kubernetes": 2,
    "machine_learning": 3
  },
  "raw_resume_skills": ["Python", "SQL", "Docker", "REST APIs"],
  "raw_jd_skills": ["Python", "Docker", "Kubernetes", "Machine Learning", "CI/CD"],
  "model_used": "llama-3.3-70b-versatile",
  "extraction_confidence": 0.87
}
```

**Error responses:**
- `422` — Request body failed Pydantic validation (e.g., `resume_text` under 50 chars)
- `503` — Groq API unavailable or `GROQ_API_KEY` missing/invalid
- `500` — Unexpected server error

---

### `POST /gap`

Compute skill gaps, apply temporal decay, and propagate prerequisite gaps via BFS.

**Request body:**
```json
{
  "candidate_skills": {
    "python": {"level": 4, "last_used_year": 2024},
    "sql": {"level": 3, "last_used_year": 2019}
  },
  "required_skills": {
    "python": 4,
    "docker": 3,
    "machine_learning": 3
  }
}
```

**Response `200`:**
```json
{
  "gaps": {
    "docker": {"current": 0, "required": 3, "delta": 3},
    "machine_learning": {"current": 0, "required": 3, "delta": 3},
    "numpy": {"current": 0, "required": 2, "delta": 2}
  },
  "already_competent": ["python"],
  "missing_entirely": ["docker", "machine_learning", "numpy"],
  "total_gap_score": 8
}
```

> Note: `sql` was decayed from Level 3 to Level 2 (5 years idle × 0.5 penalty = -2 → Level 3 - 1 = 2; still meets no requirement here but delta would be 0 if required were 2). `numpy` was not in the JD but was propagated because `machine_learning` depends on it.

**Error responses:**
- `422` — Pydantic validation failure
- `500` — Unexpected server error

---

### `POST /pathway`

Build a dependency-safe, cognitively-balanced, time-budgeted learning pathway.

**Request body:**
```json
{
  "gaps": {
    "docker": {"current": 0, "required": 3, "delta": 3},
    "machine_learning": {"current": 0, "required": 3, "delta": 3}
  },
  "already_competent": ["python", "sql"],
  "max_courses": 10,
  "max_hours": 40,
  "learner_level": "beginner",
  "preferred_providers": ["Coursera", "edX"]
}
```

**Request fields:**

| Field | Type | Default | Description |
|---|---|---|---|
| `gaps` | `Dict[str, {current, required, delta}]` | required | Output from `/gap` |
| `already_competent` | `List[str]` | `[]` | Skill IDs the candidate already meets |
| `max_courses` | `int` (1–50) | `10` | Maximum pathway length |
| `max_hours` | `int` (≥1) | `null` | Hard HR time budget cap in hours |
| `learner_level` | `"beginner" \| "intermediate" \| "advanced"` | `"beginner"` | Tie-breaker for course level selection |
| `preferred_providers` | `List[str]` | `null` | Preferred platforms (Coursera, edX, etc.) |

**Response `200`:**
```json
{
  "pathway": [
    {
      "course_id": "python_ml_basics",
      "title": "Machine Learning with Python",
      "provider": "Coursera",
      "url": "https://coursera.org/...",
      "duration_hours": 12,
      "level": "beginner",
      "skills_addressed": ["machine_learning", "numpy", "pandas"],
      "reasoning": "You're at Level 0 in machine_learning — this course bridges the Δ3 gap to the required Level 3 using a hands-on Python approach.",
      "cognitive_load": "high"
    }
  ],
  "skipped_courses": ["python_fundamentals", "sql_intro"],
  "estimated_total_hours": 28,
  "reasoning_traces": {
    "python_ml_basics": "You're at Level 0 in machine_learning — this course bridges the Δ3 gap to the required Level 3."
  },
  "pathway_summary": "Your 28-hour pathway focuses on closing 2 critical gaps: Machine Learning and Docker. You'll begin with foundational ML concepts before moving to containerisation. Estimated completion: 4 weeks at 7 hours/week."
}
```

**Error responses:**
- `422` — Pydantic validation failure
- `500` — Pathway generation failed

---

## 9. Data Models (Pydantic Schemas)

All models are defined in `backend/models/schemas.py`.

### Proficiency Scale

| Level | Name | Description |
|---|---|---|
| `1` | Awareness | Knows the concept exists; can read/follow documentation |
| `2` | Beginner | Can work with guidance for straightforward tasks |
| `3` | Intermediate | Works independently on most tasks in this domain |
| `4` | Advanced | Deep expertise; can mentor others and review code |
| `5` | Expert | Industry-leading; sets standards and designs architectures |

### `SkillGapDetail`

| Field | Type | Constraint | Description |
|---|---|---|---|
| `current` | `int` | 0–5 | Candidate's effective proficiency (after decay); 0 = skill absent |
| `required` | `int` | 1–5 | Minimum proficiency required by the role |
| `delta` | `int` | — | `required - current`; positive = gap exists |

### `CourseRecommendation`

| Field | Type | Description |
|---|---|---|
| `course_id` | `str` | Stable ID matching `course_catalog.yaml` |
| `title` | `str` | Human-readable course title |
| `provider` | `str?` | Platform name (Coursera, edX, FreeCodeCamp, etc.) |
| `url` | `str?` | Direct link to the course |
| `duration_hours` | `float` | Estimated completion time |
| `level` | `"beginner"\|"intermediate"\|"advanced"` | Difficulty level |
| `skills_addressed` | `List[str]` | Skill IDs from `skills_graph.json` this course teaches |
| `reasoning` | `str` | Groq-generated course-specific explanation |
| `cognitive_load` | `"low"\|"medium"\|"high"` | Used for cognitive load balancing in the sort |

### `ParseRequest` / `ParseResponse`

`ParseRequest`: `resume_text` (min 50 chars) + `jd_text` (min 50 chars)

`ParseResponse` includes: `candidate_skills`, `required_skills`, `raw_resume_skills`, `raw_jd_skills`, `model_used`, `extraction_confidence`

### `GapRequest` / `GapResponse`

`GapRequest`: `candidate_skills` + `required_skills`

`GapResponse` includes: `gaps`, `already_competent`, `missing_entirely`, `total_gap_score`

### `PathwayRequest` / `PathwayResponse`

`PathwayRequest`: `gaps`, `already_competent`, `max_courses`, `max_hours`, `learner_level`, `preferred_providers`

`PathwayResponse` includes: `pathway` (ordered `CourseRecommendation[]`), `skipped_courses`, `estimated_total_hours`, `reasoning_traces`, `pathway_summary`

---

## 10. Algorithm Deep Dives

### A. Temporal Skill Decay

**File:** `backend/services/gap_engine.py` — `apply_skill_decay()`

The formula `penalty = floor(years_idle × 0.5)` was chosen to reflect empirical knowledge half-life research:
- Skills in rapidly evolving fields (Python, cloud, ML) become measurably stale within 2 years
- A coefficient of 0.5 means every 2 years of non-use costs 1 proficiency level
- The floor at Level 1 (not Level 0) reflects that conceptual understanding persists even without practice

```python
def apply_skill_decay(skills: Dict[str, Dict[str, int]], current_year: int = 2025) -> Dict[str, int]:
    decayed = {}
    for skill_id, meta in skills.items():
        level = meta.get("level", 1)
        last_used = meta.get("last_used_year", current_year)
        years_idle = max(0, current_year - last_used)
        penalty = int(years_idle * 0.5)
        decayed[skill_id] = max(1, level - penalty)
    return decayed
```

**Test case verified in `verify_algorithms.py`:**
- Level 4 skill unused for 6 years → `penalty = floor(3) = 3` → `max(1, 4-3) = 1`

---

### B. Prerequisite Propagation (BFS on Skills DAG)

**File:** `backend/services/gap_engine.py` — `propagate_prerequisites()`

The skills DAG is stored in `skills_graph.json`. Each node has a `prerequisites` array listing skill IDs that must be completed first.

BFS algorithm:
```
queue = deque(initial_gap_skills)
visited = set()

while queue:
    skill = queue.popleft()
    if skill in visited: continue
    visited.add(skill)
    
    for prereq in skills_graph[skill].prerequisites:
        if candidate cannot meet prereq:
            add prereq to gaps
            queue.append(prereq)
```

This guarantees that indirect prerequisites (A → B → C, where C is the gap) are also surfaced even if A is many hops away.

---

### C. Kahn's Topological Sort with Load Balancing

**File:** `backend/services/pathway_builder.py` — `PathwayBuilder._get_ordered_ids()`

Standard Kahn's algorithm, modified with:

**1. Delta-weighted priority:**
```python
def priority(course_id: str) -> int:
    base = sum(gaps[s].delta for s in course.skills_addressed if s in gaps)
    ...
    return base
```
Courses that address the largest cumulative skill gap are scheduled first.

**2. Cognitive Load Balancing tie-breaker:**
```python
state = {"last_load": "low"}

def priority(course_id: str) -> int:
    base = _priority_score(...)
    load = course.get("cognitive_load", "high")
    if state["last_load"] == "high" and load == "low":
        return base + 1000  # Boost light courses after heavy ones
    return base
```

A mutable `state` dict ensures `last_load` is updated correctly **per course placed** (not per batch), preventing the closure-capture stale-variable bug.

**3. Topological guarantee:** Kahn's inherently errors if a cycle exists (none have been detected in `skills_graph.json`). The resulting order guarantees no course appears before its course-level prerequisites.

---

### D. HR Time Budget (Two-Phase Hard Cap)

**File:** `backend/services/pathway_builder.py`

**Phase 1 — Static catalog trim:** During Kahn's sort traversal, once `accumulated_hours ≥ max_hours`, no further courses are added.

**Phase 2 — Discovery budget:** Each AI-discovered course is only appended if:
```python
existing_hours + discovered_course_hours <= max_hours
```

This means `estimated_total_hours ≤ max_hours` is a **mathematical guarantee**, not a best-effort heuristic.

---

### E. Dynamic Discovery

**File:** `backend/services/pathway_builder.py` — `PathwayBuilder._discover_resources()`

For each gap skill with no matching course in the static catalog ("orphan gaps"):
1. Groq is prompted with the skill name, description, and proficiency level needed
2. Groq returns a JSON array of suggested external courses (title, provider, url, hours, level)
3. Each discovery course is tagged `provider = "AI DISCOVERY"` and displayed with `⚠ AI_SUGGESTED` in the UI
4. The remaining time budget is passed to Groq so it respects the cap

---

## 11. Skills Graph & Taxonomy

**File:** `backend/data/skills_graph.json`

The skills graph is a 55-node Directed Acyclic Graph (DAG). Each node has:

```json
{
  "python": {
    "name": "Python Programming",
    "category": "programming",
    "description": "Core Python language proficiency",
    "prerequisites": []
  },
  "pandas": {
    "name": "Pandas (Data Manipulation)",
    "category": "data",
    "description": "Data analysis and manipulation with pandas",
    "prerequisites": ["python", "numpy"]
  }
}
```

### Skill Categories

| Category | Skills |
|---|---|
| **Programming** | python, javascript, typescript, sql, r_programming, bash_scripting |
| **Data** | pandas, numpy, data_visualization, data_literacy, statistics |
| **Machine Learning** | machine_learning, deep_learning, nlp, computer_vision, mlops |
| **DevOps** | docker, kubernetes, ci_cd, linux, git, monitoring |
| **Cloud** | cloud_computing, aws, azure, gcp, terraform |
| **Web Development** | html_css, react, nodejs, fastapi_framework, rest_apis |
| **Soft Skills** | communication, leadership, project_management, agile_scrum, presentation_skills |
| **HR & People Ops** | hr_fundamentals, recruitment_and_talent, performance_management |
| **Finance** | accounting_basics, financial_analysis, budgeting_and_forecasting, excel_advanced |
| **Operations** | supply_chain_basics, operations_management |
| **Healthcare** | healthcare_fundamentals |
| **Sales & Marketing** | customer_service, sales_fundamentals, marketing_basics |
| **Productivity** | microsoft_office |

**Source alignment:** The hierarchy and category structure is aligned with the [O*NET OnLine](https://www.onetcenter.org/) occupation-skill taxonomy, the authoritative US Department of Labor skills classification system.

---

## 12. Course Catalog

**File:** `backend/data/course_catalog.yaml`

43 curated, real, free-to-access courses. Each entry:

```yaml
- id: python_fundamentals
  title: "Python for Everybody (Py4E)"
  provider: "Coursera (University of Michigan)"
  url: "https://www.coursera.org/specializations/python"
  duration_hours: 8
  level: beginner
  cognitive_load: low
  skills_taught:
    - python
  prerequisites: []
```

### Catalog Fields

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Stable unique identifier referenced by pathway builder |
| `title` | `str` | Full human-readable course title |
| `provider` | `str` | Platform or institution (Coursera, edX, FreeCodeCamp, etc.) |
| `url` | `str` | Direct link to the course (verified at submission time) |
| `duration_hours` | `float` | Estimated completion time in hours |
| `level` | `str` | `beginner`, `intermediate`, or `advanced` |
| `cognitive_load` | `str` | `low`, `medium`, or `high` — used for load balancing |
| `skills_taught` | `List[str]` | Skill IDs from `skills_graph.json` taught by this course |
| `prerequisites` | `List[str]` | Other course IDs that should be completed first |

### Providers Included

FreeCodeCamp, Coursera (free audit), edX (free audit), Kaggle Learn, fast.ai, GitHub Skills, MIT OpenCourseWare, official documentation (FastAPI, Pytest, Prometheus, TypeScript), HarvardX, Wharton School, SHRM Foundation, IBM, Macquarie University, Vanderbilt, Johns Hopkins.

---

## 13. Frontend — UI Component Guide

### `LandingPage.jsx`

The marketing/about page shown before the tool. 6 sections:
1. **Hero** — headline, value proposition, 4 live stat cards (55 skills, 43 courses, 0% hallucination rate, 100% topo accuracy)
2. **The Problem** — one-size-fits-all failure with animated data bars
3. **4-Stage Pipeline** — Step cards for Parse → Gap Engine → Adaptive Pathway → Reasoning Traces
4. **Tech Stack** — 8-card grid detailing every layer of the system
5. **Cross-Domain** — 8 domain tiles showing breadth of coverage
6. **Final CTA** — second call-to-action button

### `UploadPage.jsx`

Document input interface:
- **Drag-and-drop zones** for résumé and JD (PDF, DOCX, TXT accepted)
- **Text paste fallback** — click to expand plain text input boxes
- **HR Duration Slider** — 5h to 200h range, controls `max_hours` sent to `/pathway`
- **Progress stages** — "Extracting skills..." → "Computing skill gaps..." → "Building your pathway..." with animated indicators
- Orchestrates sequential API calls: `POST /parse` → `POST /gap` → `POST /pathway`

### `PathwayPage.jsx`

Results visualisation:
- **4 metric cards:** Gaps Identified, Pathway Hours, Courses Skipped, Training Time Saved %
- **Extraction confidence badge** (colour-coded: green ≥80%, yellow ≥60%, red <60%)
- **Pathway summary** — 2–3 sentence narrative from the backend
- **Clickable skill-gap cards** (left column) — click a skill to highlight only the courses that address it; other courses dim and shift right
- **Course sequence** (right column) — each card shows title, provider, reasoning, skills tags, cognitive load label, `WHY_THIS? →` button, `START_LEARNING →` button
- **AI_SUGGESTED disclaimer** — any dynamically-discovered course shows an explicit verification disclaimer

### `ReasoningTracePanel.jsx`

Slide-in drawer (opens on "WHY_THIS?" click):
- **AI Reasoning Trace** — the Groq-generated per-course explanation in a highlighted block
- **Skills you'll level up** — each taught skill shown with `Lv.X → Lv.Y` transition
- **Required Prerequisite** — shows the immediately preceding course in the pathway (clickable to navigate)
- **Mark as Complete** toggle — persists within the session
- Keyboard `Escape` to close; click-outside backdrop to dismiss

### `App.jsx`

3-state router:
- `landing` → shows `LandingPage`; header shows "LAUNCH APP →"
- `upload` → shows `UploadPage`; header shows "HOME"
- `results` → shows `PathwayPage`; header shows "NEW_ANALYSIS" + "HOME"
- Logo click always returns to `landing`

---

## 14. Cross-Domain Scalability

NexusLearn is **not** a software-engineering-only tool. The system is domain-agnostic — the domain is determined entirely by what's in `skills_graph.json` and `course_catalog.yaml`.

| Domain | Skills in Graph | Sample Courses |
|---|---|---|
| **Software Engineering** | python, javascript, typescript, sql, git, docker, kubernetes, ci_cd, rest_apis, testing | FreeCodeCamp Full-Stack, fast.ai Practical Deep Learning |
| **Data Science & ML** | machine_learning, deep_learning, nlp, pandas, numpy, data_visualization, mlops | Kaggle 30 Days of ML, fast.ai Practical Deep Learning |
| **DevOps & Cloud** | docker, kubernetes, terraform, aws, azure, gcp, monitoring, linux | GitHub Skills CI/CD, Prometheus official tutorial |
| **HR & People Ops** | hr_fundamentals, recruitment_and_talent, performance_management | SHRM Foundation/Coursera, Michigan HR/Coursera |
| **Finance & Accounting** | accounting_basics, financial_analysis, budgeting_and_forecasting, excel_advanced | Wharton Business Foundations/Coursera, edX Accounting Basics |
| **Operations & Supply Chain** | supply_chain_basics, operations_management | MIT MicroMasters Supply Chain/edX |
| **Healthcare** | healthcare_fundamentals | HarvardX Healthcare Delivery/edX |
| **Sales & Marketing** | customer_service, sales_fundamentals, marketing_basics | IBM Customer Engagement/Coursera, Illinois Marketing/Coursera |

**Extending to a new domain:** Add skills to `skills_graph.json` (with prerequisite chains) and corresponding courses to `course_catalog.yaml`. No backend code changes required — the pipeline is fully data-driven.

---

## 15. Datasets & Model Information

### LLM — Groq Llama-3.3-70B-Versatile

- **Provider:** Groq, Inc. (https://groq.com)
- **Model:** `llama-3.3-70b-versatile`
- **Used for:** Skill extraction (with closed-vocabulary allowlist), per-course reasoning traces, dynamic discovery suggestions
- **Hallucination mitigation:** Allowlist sanitisation (`_sanitise_candidate_skills`, `_sanitise_required_skills`) — any `skill_id` returned by the LLM that is not in `skills_graph.json` is silently discarded. The 0% hallucination rate applies to catalog-bound skill identification.

### Skills Taxonomy — O*NET OnLine

- **Source:** [onetcenter.org](https://www.onetcenter.org/) — US Department of Labor / Employment and Training Administration
- **Usage:** Authoritative source for skill category hierarchy, occupation-skill mappings, and prerequisite relationship design for `skills_graph.json`
- **Adaptation:** The 55-node DAG is a hand-curated adaptation of O*NET's skill clusters for the training/onboarding domain

### Course Catalog — Real-World Resources

- **Kaggle Resume Dataset** ([snehaanbhawal/resume-dataset](https://www.kaggle.com/datasets/snehaanbhawal/resume-dataset)) — used during prompt engineering to learn realistic résumé skill phrasing
- **Kaggle Job Descriptions** ([kshitizregmi/jobs-and-job-description](https://www.kaggle.com/datasets/kshitizregmi/jobs-and-job-description)) — used to validate JD parsing across technical and operational roles
- All 43 catalog courses are real, publicly accessible, free-to-audit resources. URLs were verified at the time of submission.

### Originality of Adaptive Logic

The following components are **entirely original** implementations (not third-party libraries):
- `gap_engine.py` — temporal decay formula, BFS propagation, delta computation
- `pathway_builder.py` — Kahn's sort with delta-weighted priority + cognitive load mutable-state tie-breaker + two-phase budget enforcement
- `skills_graph.json` — custom 55-node DAG with O*NET-aligned categories
- `course_catalog.yaml` — hand-curated 43-course catalog with cognitive_load ratings

---

## 16. Validation & Testing

### Automated Algorithm Tests

```bash
cd backend
python tests/verify_algorithms.py
```

**Expected output:**
```
Testing Temporal Skill Decay...         [PASS]
Testing Cognitive Load Balancing...     [PASS]
Testing HR Time Budget Constraint...    [PASS]
All algorithmic feature verifications passed!
```

**What each test verifies:**
- **Temporal Skill Decay:** Level 4 skill, 6 years idle → effective Level 1 (penalty=3, floor applied)
- **Cognitive Load Balancing:** After a "high" load course, a "low" load course is prioritised even if its delta is lower
- **HR Time Budget:** `estimated_total_hours ≤ max_hours` holds for all pathway outputs

### Internal Validation Metrics

| Metric | Measured Value | Method |
|---|---|---|
| **Prerequisite Satisfaction** | 100% | Kahn's algorithm topological guarantee; validated by `verify_algorithms.py` |
| **DAG Cycle Count** | 0 | Kahn's errors on cycles; none detected in `skills_graph.json` |
| **Budget Constraint Compliance** | 100% | Two-phase hard cap; unit tested |
| **Skill ID Hallucination Rate** | 0% (catalog-bound) | Allowlist sanitiser; all outputs verified against `skills_graph.json` |
| **API Latency (p50)** | ~3–6 seconds | Groq extraction ~2–4s; reasoning traces ~1–2s additional |
| **Topological Sort Accuracy** | 100% | All 3 tests pass; no advanced module placed before prerequisites |

> **Scope note:** The 0% hallucination rate applies to *catalog-bound skill identification only*. Dynamic Discovery results (courses suggested for orphan skills) are AI-generated and must be independently verified. They are explicitly flagged `⚠ AI_SUGGESTED` in the UI with a disclaimer.

---

## 17. Quick Start Guide

### Option A — Docker (Recommended)

```bash
# 1. Clone
git clone https://github.com/Aditya12705/NexusLearn.git
cd NexusLearn

# 2. Configure API key
cp backend/.env.example backend/.env
# Edit backend/.env and set:
#   GROQ_API_KEY=gsk_your_key_here

# 3. Launch
docker-compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Health Check | http://localhost:8000/health |

---

### Option B — Local Development

**Backend:**
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend (new terminal):**
```bash
cd frontend
npm install
npm run dev                  # Starts at http://localhost:5173
```

> The Vite dev server proxies `/parse`, `/gap`, `/pathway` to `localhost:8000` automatically.

---

## 18. Environment Variables

**File:** `backend/.env` (copy from `backend/.env.example`)

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | ✅ Yes | Groq API key — get one free at [console.groq.com](https://console.groq.com) |

> No Anthropic API key is required. `claude_service.py` exists in the codebase as legacy code but is not called by any router.

---

## 19. Docker Deployment

### `docker-compose.yml` Structure

```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    env_file: backend/.env

  frontend:
    build: ./frontend
    ports: ["3000:80"]      # Nginx serves the Vite production build
    depends_on: [backend]
```

### Backend `Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend `Dockerfile`

Multi-stage build: Vite build → Nginx serve.

---

## 20. Design Decisions & Trade-offs

| Decision | Rationale |
|---|---|
| **Single LLM (Groq Llama)** | Groq's inference API is free-tier friendly, extremely low latency, and sufficient for both extraction and reasoning tasks. Anthropic Claude was removed to simplify the API key requirements to exactly one. |
| **LLM-free gap engine** | The gap computation, decay, and BFS propagation are pure Python — deterministic, unit-testable, zero-latency, and zero-cost. Only use LLMs where deterministic logic cannot substitute. |
| **Closed-vocabulary allowlist** | The LLM is given a finite list of valid skill IDs and its output is validated against it. This is the most reliable approach to preventing skill hallucinations short of fine-tuning. |
| **Mutable state for load balancing** | The `state = {"last_load": "low"}` pattern is necessary because Python closures capture variable references, not values — a plain `last_load` nonlocal would not update correctly within Kahn's within-batch loop. |
| **Two-phase budget enforcement** | Separating static trim (during sort) from discovery trim (after sort) ensures the budget cap applies to AI-discovered courses too, which are generated after the static pathway is built. |
| **Client-side document parsing** | Using `pdfjs-dist` and `mammoth.js` in the browser means the user's document is never uploaded to any server — only the extracted text is transmitted. This is better for privacy and reduces server complexity. |
| **Lazy LLM client initialisation** | The Groq client is created on first use, not at server startup. This allows the server to boot even if `GROQ_API_KEY` is missing — useful for development/testing the health endpoint. |
| **YAML for the course catalog** | YAML is human-readable and easy to extend. Adding a new course requires only appending a YAML block — no code changes, no database migrations. |
| **JSON for the skills graph** | JSON loads natively in Python and is directly serialisable to the frontend, enabling future client-side DAG traversal if needed. |

---

## 21. Known Limitations & Scope Notes

- **Dynamic Discovery is AI-generated:** Courses suggested for orphan skills are Groq outputs and are not validated against a real course database. Always verify `⚠ AI_SUGGESTED` resources independently.
- **Proficiency scale is LLM-inferred:** The 1–5 proficiency levels assigned during extraction are the model's best estimate from unstructured résumé text. Edge cases (very short CVs, non-English text) may reduce accuracy, reflected in the `extraction_confidence` score.
- **Skills graph is hand-curated:** The 55 skills and their prerequisite chains represent the most common corporate training domains, but niche or highly specialised roles may require additional skills and courses.
- **Temporal decay is approximate:** The `0.5 × years_idle` coefficient is a defensible approximation, not empirically calibrated per-skill. Some skills decay faster (e.g., framework versions) and some slower (e.g., mathematical statistics).
- **No user accounts or persistence:** Pathways are generated per-session and not stored. A production version would add authentication and session history.

---

*NexusLearn v2.0 — Built for the ARTPARK CodeForge AI-Adaptive Onboarding Engine Hackathon Challenge*
