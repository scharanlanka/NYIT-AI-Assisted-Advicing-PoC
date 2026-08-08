# NYIT AI-Assisted Academic Advising — Full Stack

Multi-agent academic advising system built on NYIT's public 2026–2027 catalog.
FastAPI backend + Next.js frontend. Runs out-of-the-box in template mode without
API keys.

> **Disclaimer:** Demo using NYIT's public 2026–2027 course catalog. All student
> profiles are **synthetic**. Not integrated with any NYIT student information system.

## 🚀 Run it (two terminals)

Run these commands from the project root: `nyit-fullstack/`

### Terminal 1 — Backend (FastAPI)

```bash
python -m venv backend/.venv && source backend/.venv/bin/activate    # Windows: backend\.venv\Scripts\activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8001
```

Backend is at http://localhost:8001  ·  API docs at http://localhost:8001/docs

If you are already inside `backend/`, use:

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd ..
uvicorn backend.main:app --reload --port 8001
```

### Terminal 2 — Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

Frontend at http://localhost:3001. Open it in your browser — that's the whole demo.

### Optional — enable real LLM responses

Copy `.env.example` to `.env` in the project root (or set env vars directly) and add
**one** of:

```bash
export ANTHROPIC_API_KEY=sk-ant-...    # preferred
# OR
export OPENAI_API_KEY=sk-...
```

Then restart the backend. The banner at the top of the app will switch from
"template mode" to "LLM connected".

## Architecture

```
┌──────────────────────┐            ┌────────────────────────────┐
│  Next.js frontend    │  HTTP      │  FastAPI backend           │
│  (React + Tailwind)  │───────────▶│                            │
│  localhost:3001      │            │  Multi-agent orchestrator: │
│                      │            │    Router → Specialist     │
│  Client-side state:  │            │                            │
│  - prefs overrides   │            │  Deterministic services:   │
│  - pathway overrides │            │    Prereq engine           │
│  - snapshot for diff │            │    Pathway recommender     │
│                      │            │    Completion analyzer     │
└──────────────────────┘            │    Operation validator     │
                                    │    History reconstructor   │
                                    │                            │
                                    │  LLM providers:            │
                                    │    Anthropic / OpenAI /    │
                                    │    Template fallback       │
                                    └────────────────────────────┘
```

**Key design decisions:**

1. **State lives client-side** — the backend is stateless. The frontend keeps
   `pathwayOverrides` and `prefsOverrides` in React state and sends them with
   every pathway request. This makes the backend cache-friendly and lets a single
   deployment serve many concurrent sessions.

2. **Multi-agent architecture** — one Router Agent classifies user intent,
   then delegates to one of four specialist agents (Plan Editor, Preferences
   Editor, Q&A) with focused prompts and bounded action spaces.

3. **Deterministic engines + LLM specialists** — prereq resolution, pathway
   planning, degree completion analysis, and operation validation are all
   pure Python graph/set algorithms. LLMs only do NL parsing, explanation,
   memo drafting, and chat.

4. **Guardrail validator on every AI proposal** — every operation the AI
   proposes is re-validated against program-scope, prereq, and semester-offering
   rules before the user can approve it. Nothing bypasses the validator.

## Features

Five tabs, all wired to the FastAPI backend:

| Tab | What it does |
|-----|--------------|
| **Overview** | Student profile, progress bar, editable preferences, requirement blocks with completion status |
| **Academic Journey** | Full timeline (past + current + planned), degree completion strip, AI plan editor with routing transparency, diff banner showing what changed after any edit, manual per-course move/remove controls |
| **Prerequisite Explorer** | SVG-rendered prereq graph filtered by program universe. Four-state node styling (target / completed / in progress / needed) |
| **Chat** | Natural-language Q&A grounded in the student's actual pathway |
| **Advisor Summary** | Printable memo combining the plan with LLM-drafted rationale |

## The multi-agent flow

Every AI edit request goes through the same chain:

```
  User query
      │
      ▼
  ┌──────────┐   Classifies intent into: PLAN_MOVE, CONCENTRATION,
  │  Router  │   PREFERENCES, QUESTION, or CLARIFICATION_NEEDED.
  │  Agent   │   Small prompt, fast, cheap.
  └────┬─────┘
       │
       ▼
  ┌──────────────────────┐
  │  One of 4 specialists │
  │                       │
  │  • Plan Editor        │  → structured course-level ops
  │  • Preferences Editor │  → concentration / prefs changes
  │  • Q&A Agent          │  → answers, no changes proposed
  │  • Clarification      │  → asks the user to rephrase
  └───────────┬───────────┘
              │
              ▼
  ┌────────────────────┐
  │ Guardrail validator│  Every proposed operation checked against:
  │                    │  1. Course exists in catalog
  │                    │  2. Course in program universe (no cross-program)
  │                    │  3. Semester offers this course (season match)
  │                    │  4. Prereqs satisfied by destination term
  │                    │  5. Cannot modify past/current term
  └──────────┬─────────┘
             │
             ▼
  ┌────────────────────┐
  │ Preview + confirm  │  User sees each op with ✓/✕ + reason.
  │                    │  Only approved ops apply to state.
  └────────────────────┘
```

If the router returns low confidence (<60%), the system surfaces the ambiguity
and asks the user to rephrase — instead of committing to a wrong specialist.

## Programs and students

**Undergraduate:**
- Computer Science, B.S. — 122 cr, 4 concentrations (AI, Big Data, Network Security, General)
- Information Technology, B.S. — 120 cr, Info/Network Security Option
- Electrical & Computer Engineering, B.S. — 132 cr

**Graduate:**
- Computer Science, M.S. — 30 cr
- Data Science, M.S. — 30 cr
- Mechanical Engineering, M.S. — 30 cr, 4 concentrations

**14 synthetic students** including two first-semester students (Sam Patel CS BS
freshman, Riya Sharma incoming CS MS) so you can demo day-1 advising alongside
mid-program students.

## API endpoints

Interactive docs at http://localhost:8001/docs after the backend starts.

**Data:**
- `GET /health`
- `GET /programs` · `GET /programs/{id}` · `GET /programs/{id}/universe`
- `GET /students` · `GET /students/{id}`
- `GET /courses` · `GET /courses/{id}`
- `GET /courses/{id}/prereq-chain` · `GET /courses/{id}/dependents`

**Pathway (stateless — client owns overrides):**
- `POST /pathway/with-overrides` — main endpoint used by the frontend
- `POST /pathway/validate-operation`

**Multi-agent:**
- `POST /agents/orchestrate` — router → specialist chain, returns validated ops
- `POST /agents/explain` — plan rationale
- `POST /agents/advisor-summary` — advisor memo
- `POST /agents/chat` — free-form chat grounded in the plan

## Project structure

```
nyit-fullstack/
├── README.md
├── .env.example
├── .gitignore
├── backend/
│   ├── requirements.txt
│   ├── main.py                    # FastAPI app
│   ├── models.py                  # Pydantic schemas
│   ├── prerequisite_engine.py     # Prereq graph resolver
│   ├── pathway_recommender.py     # Semester-by-semester planner
│   ├── program_universe.py        # Program-relevant course sets
│   ├── operations.py              # Validate + apply edits, compute diffs
│   ├── completion.py              # Degree completion analyzer
│   ├── history.py                 # Historical semester reconstruction
│   ├── llm_service.py             # Async LLM wrapper (Anthropic/OpenAI/template)
│   ├── agents/
│   │   ├── context.py             # Curriculum context (non-LLM)
│   │   ├── router.py              # Router Agent
│   │   ├── plan_editor.py         # Plan Editor Agent
│   │   ├── preferences_editor.py  # Preferences Editor Agent
│   │   ├── qa.py                  # Q&A Agent
│   │   └── orchestrator.py        # Routes query through the chain
│   └── data/
│       ├── raw_curricula/         # One JSON per program (NYIT catalog)
│       ├── course_catalog.json    # Merged catalog (124 courses)
│       ├── programs.json          # 6 program structures
│       └── sample_students.json   # 14 synthetic profiles
└── frontend/
    ├── package.json
    ├── next.config.js
    ├── tsconfig.json
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx               # Main orchestrator
    │   └── globals.css
    ├── components/
    │   ├── Sidebar.tsx
    │   ├── Overview.tsx           # Overview tab
    │   ├── Journey.tsx            # Academic Journey tab
    │   ├── SemesterCard.tsx
    │   ├── PrereqExplorer.tsx
    │   ├── Chat.tsx
    │   └── AdvisorSummary.tsx
    └── lib/
        ├── types.ts               # TypeScript types matching backend
        └── api.ts                 # API client
```

## Demo script for stakeholders

1. **Alex Morgan (CS_BS, AI concentration)** — Overview shows ~91% amber
   completion, 12 requirement blocks on track, 2 with known limitations
   (seminar placeholders, open-ended electives)
2. **Academic Journey tab** — see past terms (reconstructed), current term
   (in progress), planned future terms
3. **Ask AI:** *"actually I'd rather focus on big data than AI — can you switch me
   and update my plan"*
   - Watch: 🔀 Router → CONCENTRATION (95%) → 🤖 Preferences Editor Agent
   - Preview shows: ✓ Switch concentration → Big Data Management and Analytics
   - Click Apply → diff banner shows added/removed/moved courses
   - Degree completion stays at ~91% amber — the AI didn't break the degree
4. **Ask AI:** *"move CSCI 415 to Spring 2028 — I want a lighter Fall"*
   - Router → PLAN_MOVE → Plan Editor Agent
   - Small, focused change; diff shows one move
5. **Try Ryan O'Sullivan (MENG_MS)** — Prerequisite Explorer scope
   filter shows only MENG courses. No CSCI contamination
6. **Try Riya Sharma (CS_MS incoming)** — brand-new grad student, empty past,
   3-course first term, plan spans 2 years

## Known M4 items (documented, not hidden)

Both surface honestly in the Degree Completion strip:

1. **Placeholder seminar codes** (`ICBS 3XX`, etc.) — the recommender skips
   wildcards. Production version needs a small seminar picker.
2. **Elective sub-categorization** — treats "Electives (15 cr)" as a single
   credit target. Real degree audits split into Math/Sci / General / Liberal
   Arts sub-buckets and validate each course's category.

The story: *"here's what we'd tighten before production"* is stronger than
pretending these gaps don't exist.

## Data sources

Everything sourced from NYIT public resources:
- `catalog.nyit.edu/engineering/*` — six program curricula (2026-2027)
- `nyit.edu/advising/semester_maps` — official semester-by-semester progressions
- `site.nyit.edu/files/advising/semester_maps_2022/*.pdf` — Semester Map PDFs

Student profiles are entirely synthetic — no real student data.
