# DataPulse — Talk to Your Data, Get Answers You Trust

<p align="center">
  <img src="docs/images/landing.png" alt="DataPulse Landing" width="720" />
</p>

<p align="center">
  <strong>Natural language data analysis for everyone. No SQL. No formulas. No training.</strong><br/>
  Built for <a href="#">NatWest Group — Code for Purpose India Hackathon</a> · Talk to Data track
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/react-18-61DAFB?logo=react&logoColor=white" />
  <img src="https://img.shields.io/badge/DuckDB-in--memory-FFC107?logo=duckdb&logoColor=black" />
  <img src="https://img.shields.io/badge/LLM-Groq%20(Llama%203.1)-green?logo=meta&logoColor=white" />
  <img src="https://img.shields.io/badge/license-Apache%202.0-lightgrey" />
</p>

---

## Overview

Business analysts and team leads need quick data insights but lack SQL skills or access to BI tools. DataPulse bridges this gap: upload any CSV, ask questions in plain English, and get instant answers with charts, KPIs, and explanations — all running **100% locally** with zero data leaving the device.

The system uses a **three-agent query pipeline** (inspired by [Azure SQL's collaborating agents pattern](https://devblogs.microsoft.com/azure-sql/a-story-of-collaborating-agents-chatting-with-your-database-the-right-way/)) paired with a **Snowflake-format semantic layer** to ensure consistent, auditable metric definitions across all queries.

**Who is this for?** Non-technical business users in banking — analysts, team leads, operations staff — who need to interrogate data without waiting for a BI team.

---

## Features

- **Natural language querying** — Ask questions in plain English; the system translates them into SQL, executes, and explains the results.
- **Three-agent pipeline** — Agent 1 (Analyst) classifies intent and selects relevant schema; Agent 2 (SQL Writer) generates focused DuckDB SQL seeing only relevant columns; Agent 3 (Explainer) produces KPIs, charts, and plain-English explanations.
- **Deterministic driver analysis** — "Why did X change?" triggers a pure-SQL engine that computes exact contribution percentages per dimension value. No LLM guesswork — every number is verifiable.
- **SQL safety layer** — Every LLM-generated query passes through a sanitizer that blocks `DROP`, `DELETE`, `TRUNCATE`, `INSERT`, `UPDATE`, and comment injection before execution. Security matters in a banking context.
- **Snowflake-format semantic layer** — Auto-generated data dictionary with metrics (SQL expressions + synonyms), dimensions (sample values), and time dimensions (granularity detection). Editable in-app.
- **Auto-dashboard** — Instant visual overview after upload: KPI cards with sparklines, time trend chart, dimension breakdown — zero LLM calls needed.
- **Visual-first answers** — Every response follows a structured hierarchy: KPI cards → hero chart → insight line → explanation → follow-up suggestions.
- **Disambiguation** — When questions are ambiguous, the system asks clarifying questions with clickable options instead of guessing.
- **4 analysis modes** — What Changed, Compare, Breakdown, Summary (plus Auto-detect).
- **AI-generated follow-ups** — Context-aware next questions after each answer.
- **Query caching** — Repeated questions return cached results instantly (10-min TTL).
- **Data lineage & transparency** — Collapsible panel shows: intent classification, confidence level, SQL used, metric expressions, and data coverage percentage.
- **Copy as markdown** — One-click export of any answer.
- **Privacy-first** — All data processed locally via DuckDB in-memory engine. Nothing is transmitted externally except LLM prompts (which contain schema metadata, never raw data).
- **3 banking sample datasets** — SME Lending, Customer Support, Digital Banking — each with embedded anomalies and stories for compelling demos.

---

## Demo Walkthrough

### 1. Upload & Auto-Dashboard
Upload a CSV (or pick a sample) → DataPulse automatically builds a semantic layer and generates an overview dashboard with KPI cards, trend charts, and dimension breakdowns.

<p align="center">
  <img src="docs/images/dashboard.png" alt="Auto Dashboard" width="680" />
</p>

### 2. Ask a Question — "Why did revenue drop last month?"
The three-agent pipeline classifies this as a "change" intent, runs deterministic driver analysis, and returns:

<p align="center">
  <img src="docs/images/change_query.png" alt="Change Analysis" width="680" />
</p>

- **KPI cards** showing the metric before/after
- **Waterfall chart** showing each dimension's contribution to the change
- **Plain-English explanation** narrating the real numbers
- **Follow-up suggestions** for deeper analysis

### 3. Compare — "Compare North vs South approvals"

<p align="center">
  <img src="docs/images/compare_query.png" alt="Compare Analysis" width="680" />
</p>

### 4. Transparency Panel
Every answer has a collapsible "How was this answered?" panel showing the SQL query, confidence score, metric definitions used, and data coverage.

<p align="center">
  <img src="docs/images/transparency.png" alt="Transparency Panel" width="680" />
</p>

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Free Groq API key → [console.groq.com/keys](https://console.groq.com/keys)

### One-Command Setup

```bash
# Clone the repository
git clone https://github.com/Suryanshu01/datapulsee.git
cd datapulsee

# Linux / Mac
chmod +x scripts/start.sh && ./scripts/start.sh

# Windows
.\scripts\start.bat
```

The script will create a virtual environment, install dependencies, prompt for your API key, start the backend on port 8000, and the frontend on port 3000.

### Manual Setup

```bash
# 1. Set up environment
cp .env.example .env
# Edit .env → add your GROQ_API_KEY

# 2. Backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd src/backend
uvicorn main:app --port 8000 &

# 3. Frontend
cd ../../src/frontend
npm install
npm run dev

# 4. Open http://localhost:3000
```

---

## Tech Stack

| Technology | Role | Why This Choice |
|-----------|------|-----------------|
| **DuckDB** | SQL engine | Zero-config in-memory OLAP. Handles `GROUP BY`, window functions, and `FULL OUTER JOIN` on CSV data — faster than SQLite for analytical queries. |
| **Groq (Llama 3.1 8B)** | LLM provider | Free-tier with 500K tokens/day. Sub-second inference latency. Easily swappable to 70B for better SQL quality. |
| **FastAPI** | Backend framework | Async Python with auto-generated API docs at `/docs`. Pydantic validation on all endpoints. |
| **React 18 + Vite** | Frontend | Component-based UI with instant hot reload. Lean — no Redux, no heavy state libraries. |
| **Recharts** | Charts | Composable React chart library with built-in animations. Supports all chart types needed (bar, line, area, donut). |
| **Custom SVG** | Waterfall & Sparklines | Hand-built SVG components for driver waterfall cascades and KPI sparklines — Recharts doesn't support these natively. |

---

## Architecture

### Three-Agent Pipeline

Our query pipeline uses a collaborating agents pattern inspired by [Azure SQL's approach](https://devblogs.microsoft.com/azure-sql/a-story-of-collaborating-agents-chatting-with-your-database-the-right-way/). The key insight: **Agent 2 (SQL Writer) sees only the relevant columns**, not the entire schema. This dramatically reduces column hallucination — the most common failure mode in text-to-SQL systems.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER QUESTION                                │
│                "Why did revenue drop last month?"                    │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Query Cache │──── Cache hit? → Return instantly
                    └──────┬──────┘
                           │ miss
                    ┌──────▼──────┐
                    │   Agent 1   │  Receives: full semantic layer
                    │  (Analyst)  │  Returns:  intent=change, relevant_metrics=[revenue],
                    │             │            relevant_dimensions=[region], plan
                    └──────┬──────┘
                           │
              ┌────────────┤ intent == "change"?
              │            │
        ┌─────▼─────┐  ┌──▼───────────┐
        │  Driver    │  │   Agent 2    │  Receives: ONLY relevant columns' schema
        │  Analysis  │  │ (SQL Writer) │  Returns:  DuckDB SQL
        │ (pure SQL) │  └──────┬───────┘
        └─────┬─────┘         │
              │          ┌────▼────┐
              │          │ Execute │──── Fails? → Auto-retry with error context
              │          └────┬────┘
              │               │
              └───────┬───────┘
                      │
               ┌──────▼──────┐
               │   Agent 3   │  Receives: question + SQL + results + driver data
               │ (Explainer) │  Returns:  explanation, KPIs, chart config, follow-ups
               └──────┬──────┘
                      │
        ┌─────────────▼─────────────┐
        │     VISUAL-FIRST ANSWER   │
        │  KPIs → Chart → Insight   │
        │  → Explanation → Lineage  │
        └───────────────────────────┘
```

### Semantic Layer

Mirrors [Snowflake Cortex Analyst's semantic model specification](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/semantic-model-spec):

- **Metrics**: SQL expressions (`SUM("revenue")`), human-readable names, synonyms for fuzzy matching
- **Dimensions**: Categorical columns with sample values (so the LLM generates correct `WHERE` clauses)
- **Time Dimensions**: Date/time columns with auto-detected granularity (daily/weekly/monthly)

The semantic layer is auto-generated on upload and editable in-app via the Data Dictionary panel.

### Design Decisions

| Decision | Trade-off | Rationale |
|----------|-----------|-----------|
| Two-agent split for SQL | Extra LLM call per query | Agent 2 sees only relevant columns → 3× fewer column hallucinations in testing |
| Deterministic driver analysis | Only works for "change" intent | Eliminates LLM hallucination for the most trust-sensitive query type |
| DuckDB over SQLite | Slightly larger binary | GROUP BY + window functions run 5-10× faster on analytical queries |
| System fonts over Google Fonts | Less typographic control | Zero external requests, instant load, privacy-first |
| Groq over OpenAI | Smaller model (8B vs GPT-4) | Free tier, sub-second latency, good enough for structured SQL generation |
| In-memory only | No persistence across sessions | Simplicity, privacy — no data written to disk |

### Data Flow Diagram

See [`docs/architecture.md`](docs/architecture.md) for full Mermaid diagrams including the sequence diagram and class diagram.

---

## Project Structure

```
datapulsee/
├── src/
│   ├── backend/
│   │   ├── main.py                    # FastAPI app, CORS, routes, health check
│   │   ├── config.py                  # All settings and constants in one place
│   │   ├── routes/
│   │   │   ├── upload.py              # POST /api/upload, GET /api/samples
│   │   │   ├── query.py               # POST /api/ask — three-agent pipeline
│   │   │   ├── semantic.py            # GET/PUT /api/semantic-layer
│   │   │   └── dashboard.py           # GET /api/dashboard, /api/story
│   │   ├── services/
│   │   │   ├── query_pipeline.py      # Three-agent orchestration
│   │   │   ├── driver_analysis.py     # Deterministic driver engine (pure SQL)
│   │   │   ├── schema_analyzer.py     # CSV type detection, stats, date handling
│   │   │   ├── semantic_engine.py     # Semantic layer generation
│   │   │   ├── chart_recommender.py   # Chart type validation and repair
│   │   │   └── explanation.py         # Data story generation
│   │   ├── utils/
│   │   │   ├── llm_client.py          # Groq API wrapper with retry/backoff
│   │   │   ├── duckdb_manager.py      # Session-scoped DuckDB connections
│   │   │   ├── cache.py               # NL→result cache (10-min TTL)
│   │   │   └── sql_sanitizer.py       # SQL safety validation
│   │   └── models/
│   │       └── schemas.py             # Pydantic request/response models
│   └── frontend/
│       └── src/
│           ├── App.jsx                # Landing page + workspace layout
│           ├── components/
│           │   ├── ChatInterface.jsx   # Chat with visual-first answer layout
│           │   ├── AutoDashboard.jsx   # Auto-generated overview dashboard
│           │   ├── SemanticLayer.jsx   # Data dictionary editor
│           │   ├── DataPreview.jsx     # Schema + stats + sample rows
│           │   ├── UploadPanel.jsx     # Drag-drop upload + sample datasets
│           │   ├── TrustPanel.jsx      # Data lineage display
│           │   └── charts/
│           │       ├── ChartRenderer.jsx    # Chart type router
│           │       ├── KPICard.jsx          # Animated counter with sparkline
│           │       ├── WaterfallChart.jsx    # Custom SVG waterfall
│           │       ├── AnimatedBar.jsx      # Sequential bar reveal
│           │       ├── AnimatedLine.jsx     # Line with draw effect
│           │       └── AnimatedDonut.jsx    # Donut with segment unfold
│           ├── utils/
│           │   └── formatNumber.js    # Smart number formatting (K/M/B)
│           └── index.css              # Full design system (NatWest-inspired tokens)
├── tests/
│   ├── test_backend.py                # 36 tests: endpoints, pipeline, cache, samples
│   ├── test_driver_analysis.py        # Driver engine unit tests
│   └── test_sql_sanitizer.py          # SQL safety validation tests
├── scripts/
│   ├── start.sh                       # One-command setup (Linux/Mac)
│   ├── start.bat                      # One-command setup (Windows)
│   └── generate_samples.py            # Banking sample dataset generator
├── assets/samples/                    # Pre-generated banking CSV datasets
├── docs/
│   ├── architecture.md                # Full Mermaid diagrams
│   └── data_flow.md                   # Data flow documentation
├── .env.example                       # Required environment variables
├── requirements.txt                   # Python dependencies
└── LICENSE                            # Apache 2.0
```

---

## Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests
pytest tests/ -v --tb=short

# Run specific test modules
pytest tests/test_sql_sanitizer.py -v
pytest tests/test_driver_analysis.py -v
```

---

## Limitations

- **Single table per session** — Currently supports one CSV at a time (no joins across files).
- **No persistent storage** — Sessions are in-memory; data is cleared on server restart.
- **LLM rate limits** — Groq free tier has daily token limits; sustained heavy usage may hit throttling.
- **No authentication** — Designed for local single-user use, not multi-tenant deployment.
- **English only** — Natural language processing is optimized for English questions.
- **No file export** — Charts and answers can be copied as markdown but not exported as PDF/Excel.

---

## Future Improvements

- **Multi-table support** — Upload multiple CSVs and query across them with auto-detected join keys.
- **Conversation memory** — Let the system reference previous questions for contextual follow-ups.
- **Export to PDF/Excel** — One-click report generation from chat history.
- **Streaming responses** — Show partial results as each agent completes (SSE/WebSocket).
- **Model flexibility** — Let users pick between speed (8B) and accuracy (70B) per question.
- **Scheduled summaries** — Auto-generate daily/weekly insight emails from uploaded datasets.

---

## License

Apache 2.0 — see [LICENSE](LICENSE)
