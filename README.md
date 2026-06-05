<p align="center">
  <img src="https://img.shields.io/badge/🧭-DataPilot_AI-6366F1?style=for-the-badge" alt="DataPilot AI" />
</p>

<h1 align="center">🧭 DataPilot AI</h1>

<h3 align="center">Natural Language → SQL · Execute · Analyze · Visualize</h3>

<p align="center"><strong>Talk to your database in plain English. Get SQL, results, and business insights in seconds.</strong></p>

<p align="center">
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"></a>
  <a href="https://streamlit.io"><img src="https://img.shields.io/badge/Streamlit-Frontend-FF4B4B?style=flat-square&logo=streamlit&logoColor=white" alt="Streamlit"></a>
  <a href="https://github.com/langchain-ai/langgraph"><img src="https://img.shields.io/badge/LangGraph-Orchestration-412991?style=flat-square" alt="LangGraph"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License"></a>
</p>

---

## What is DataPilot AI?

DataPilot AI is a production-ready **natural language database query engine**. Connect it to any MySQL or PostgreSQL database and ask questions in plain English — DataPilot translates your question into optimized SQL, executes it, and returns structured results alongside AI-generated business insights, trend cards, and chart recommendations.

**No SQL knowledge required. No manual query writing. Just ask.**

---

## Core Capabilities

| Capability | Details |
|---|---|
| **NL → SQL Generation** | LangGraph multi-agent pipeline with self-correction (up to 5 retries) |
| **Multi-Provider LLM** | OpenRouter, OpenAI, Gemini, Groq, NVIDIA — auto-fallback between providers |
| **Query Complexity Routing** | Zero-latency regex classifier routes EASY / MEDIUM / HARD to optimized prompt strategies |
| **Speed Engine** | Two-phase execution: SQL + data in ≤5s; explanation + insights in parallel background threads |
| **SSE Streaming** | Real-time Server-Sent Events pipeline for live stage-by-stage progress updates |
| **AI Insight Cards** | Automatic trend detection, top-performer identification, and anomaly alerts |
| **Executive Narrative** | LLM-generated 3-5 sentence business summary of every result set |
| **Chart Recommendation** | Intelligent chart type selection (bar, line, pie, scatter, table) |
| **Query History** | Full audit trail with replay and export capabilities |
| **Export Engine** | CSV, Excel (xlsx), and PDF export with role-based access control |
| **Voice Input** | Speech-to-text query normalization via LLM cleaning pipeline |
| **Column Validator** | Fuzzy correction of hallucinated or misspelled column names post-generation |
| **Multi-Level Cache** | TTL-based caching for schema context, SQL results, explanations, insights, and charts |
| **Intent Classification** | Conversational vs Database query detection for a better UX, avoiding unnecessary SQL generation |
| **Large File Support** | Upload support for up to 500MB files for CSV, SQLite, DB, and SQL formats |
| **Extended Sessions** | Configurable, secure 7-day extended JWT login sessions for better usability |
| **Mobile-First UI** | Full responsive optimization (320px–480px) with segmented controls, horizontal tag quick suggestions, vertical stats grid, and bottom-sheet reconnect modals |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Streamlit Frontend                 │
│  Dashboard · Query History · Settings · Profile      │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼──────────────────────────────┐
│              FastAPI Backend  /api/v1                │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │            DataPilot Speed Engine            │   │
│  │  POST /query/fast-analyze                    │   │
│  │  POST /query/stream-analyze  (SSE)           │   │
│  │                                              │   │
│  │  Phase 1 (≤5s)                               │   │
│  │  Classify → Schema → Generate SQL → Execute  │   │
│  │                                              │   │
│  │  Phase 2 (parallel, background)              │   │
│  │  Explanation ‖ Insights ‖ Chart              │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌─────────────────┐  ┌────────────────────────┐    │
│  │  LangGraph      │  │  Multi-Provider LLM    │    │
│  │  Workflow       │  │  OpenRouter / OpenAI   │    │
│  │  (6-stage DAG)  │  │  Gemini / Groq / NVDIA │    │
│  └─────────────────┘  └────────────────────────┘    │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │           Database Layer                    │    │
│  │  MySQL · PostgreSQL · SQLite                │    │
│  │  Schema Inspector · Query Executor          │    │
│  │  Connection Manager · TTL Cache             │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

### AI Pipeline (LangGraph DAG)

```
User Query
    │
    ▼
[Query Enhancement]   — intent expansion, analytics hint injection
    │
    ▼
[Schema Analysis]     — dynamic schema introspection + AI-context build
    │
    ▼
[SQL Generation]      — tiered prompt strategy (SIMPLE/MEDIUM/ANALYTICAL)
    │                   self-corrects up to 5× on validation failure
    ▼
[Validation]          — column validator + semantic SQL checker
    │
    ▼
[Explanation]         — plain-English walkthrough of the generated SQL
    │
    ▼
[Visualization]       — rule-based + LLM chart type recommendation
    │
    ▼
[Analytics Insights]  — trend, top-performer, anomaly detection + LLM narrative
    │
    ▼
Structured Response
```

---

## Tech Stack

**Backend**
- [FastAPI](https://fastapi.tiangolo.com) — async REST API with OpenAPI docs
- [LangGraph](https://github.com/langchain-ai/langgraph) — stateful multi-agent AI orchestration
- [LangChain](https://github.com/langchain-ai/langchain) — LLM abstractions and prompt management
- [SQLAlchemy](https://www.sqlalchemy.org) — database engine abstraction
- [Pydantic v2](https://docs.pydantic.dev) — request/response schema validation
- [Alembic](https://alembic.sqlalchemy.org) — database migration management
- [PyJWT](https://pyjwt.readthedocs.io) — JWT authentication

**AI / LLM**
- OpenRouter (default gateway — routes to Gemini, GPT, Claude, etc.)
- Google Gemini (`gemini-2.5-flash`)
- OpenAI (`gpt-4o`, `gpt-4-turbo`)
- Groq (`llama-3.3-70b-versatile`) — ultra-fast inference
- NVIDIA NIM (`nemotron-3-super-120b`)

**Frontend**
- [Streamlit](https://streamlit.io) — premium dark-theme dashboard
- [Plotly](https://plotly.com) — interactive chart rendering
- Custom CSS (Inter + JetBrains Mono typography, glassmorphism UI)

**Databases Supported**
- MySQL 5.7+ / 8.0+
- PostgreSQL 12+
- SQLite (file-based, for development)

---

## Quickstart

### Prerequisites

- Python 3.11+
- MySQL or PostgreSQL instance (the database you want to analyze)
- An API key for at least one LLM provider (OpenRouter recommended)

### 1. Clone the repository

```bash
git clone https://github.com/your-org/datapilot-ai.git
cd datapilot-ai
```

### 2. Configure environment

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and set:

```env
# Required — at minimum one LLM key
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-or-xxxxxxxx   # OpenRouter key works here automatically

# Or use Gemini
GEMINI_API_KEY=your-gemini-key

# JWT secret (generate with: python -c "import secrets; print(secrets.token_hex(32))")
JWT_SECRET_KEY=your-64-char-secret

# Your target database
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your-password
MYSQL_DATABASE=your-database
```

### 3. Install dependencies & start backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Start frontend

```bash
cd frontend
pip install -r requirements.txt
python -m streamlit run app.py
```

Open **http://localhost:8501** — sign up, connect your database, and start querying.

---

## Docker Deployment

```bash
# Build and run both services
docker-compose up --build

# Backend API:   http://localhost:8000
# API Docs:      http://localhost:8000/api/v1/docs
# Frontend:      http://localhost:8501
```

`docker-compose.yml` is in the `backend/` directory. The backend uses a multi-stage build with a non-root user for security.

---

## API Reference

Interactive docs available at **`http://localhost:8000/api/v1/docs`** after startup.

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/register` | Create a new user account |
| `POST` | `/api/v1/auth/login` | Authenticate and receive JWT |
| `POST` | `/api/v1/database/connect` | Connect to a target database |
| `GET`  | `/api/v1/database/schema` | Inspect the connected database schema |
| `POST` | `/api/v1/query/generate` | Generate SQL from natural language |
| `POST` | `/api/v1/query/execute` | Execute a SQL query securely |
| `POST` | `/api/v1/query/fast-analyze` | **Full pipeline** — NL → SQL → Execute → Insights in one call |
| `POST` | `/api/v1/query/stream-analyze` | SSE streaming with live stage updates |
| `POST` | `/api/v1/query/insights` | Generate AI insights for an existing result set |
| `GET`  | `/api/v1/history` | Retrieve query history |
| `POST` | `/api/v1/export/csv` | Export results as CSV |
| `POST` | `/api/v1/export/excel` | Export results as Excel |
| `POST` | `/api/v1/export/pdf` | Export results as PDF |
| `GET`  | `/api/v1/health` | Health check + connection count |

### Fast Analyze — Example

```bash
curl -X POST http://localhost:8000/api/v1/query/fast-analyze \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "user_query": "Show me the top 10 customers by revenue this year",
    "explanation_mode": "Detailed",
    "auto_insights": true,
    "row_limit": 100
  }'
```

**Response:**
```json
{
  "success": true,
  "complexity": "medium",
  "sql": "SELECT c.customer_id, ...",
  "columns": ["customer_id", "customer_name", "total_revenue"],
  "rows": [...],
  "row_count": 10,
  "execution_duration": 0.043,
  "explanation": "This query joins customers with orders...",
  "insight_cards": [
    {"type": "top_performer", "title": "Top Performer", "body": "Acme Corp leads with $2.4M revenue", "severity": "positive"}
  ],
  "narrative": "Revenue is concentrated in 3 enterprise accounts...",
  "recommended_chart": "bar_chart",
  "timing": {"complexity_ms": 0.4, "sql_gen_ms": 1823, "sql_exec_ms": 43, "total_ms": 2891}
}
```

---

## LLM Provider Configuration

DataPilot supports hot-swapping between providers. Set `LLM_PROVIDER` in `.env` and the corresponding API key:

| Provider | Env Variable | Default Model |
|----------|-------------|---------------|
| `openrouter` | `OPENROUTER_API_KEY` | `google/gemini-2.5-flash-001` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o` |
| `gemini` | `GEMINI_API_KEY` | `gemini-2.5-flash` |
| `groq` | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |
| `nvidia` | `NVIDIA_API_KEY` | `nvidia/nemotron-3-super-120b` |

**Automatic fallback:** If the configured provider's key is missing or returns an error (402, 429, 5xx), DataPilot automatically falls back to the next available configured provider — zero downtime.

**OpenRouter auto-detection:** If you paste an OpenRouter key (`sk-or-*`) into any provider's field, DataPilot detects and routes through OpenRouter automatically.

---

## Security Model

- **JWT authentication** on all endpoints (7-day extended access tokens, for uninterrupted workflow)
- **SELECT-only enforcement** — all queries are validated before execution; DDL and DML are blocked by default (configurable)
- **Zero-latency interception** — destructive actions (ALTER, DROP, DELETE, UPDATE) are intercepted at both the intent detection stage and execution validator to immediately return friendly read-only messages without database load or visual glitches.
- **Query timeout** — 30-second hard cap per query (configurable)
- **Row limit** — max 10,000 rows returned; max 50,000 rows for export
- **Blocked keywords** — regex-based injection pattern detection
- **Non-root Docker** — production container runs as `appuser` (UID 1001)
- **CORS** — configurable allowed origins
- **Audit logging** — every query execution logged with user ID, SQL, status, and duration

---

## Project Structure

```
datapilot-ai/
├── backend/
│   ├── app/
│   │   ├── agents/                  # AI agent orchestration
│   │   │   ├── langgraph_workflow.py # 6-stage LangGraph DAG
│   │   │   ├── query_agent.py        # Main pipeline entry point
│   │   │   ├── analytics_agent.py    # Business insight generation
│   │   │   ├── visualization_agent.py# Chart recommendation
│   │   │   ├── validator_agent.py    # SQL validation + confidence scoring
│   │   │   ├── explanation_agent.py  # Plain-English SQL explanation
│   │   │   └── voice_agent.py        # Voice query normalization
│   │   ├── api/routes/              # FastAPI route handlers
│   │   │   ├── fast_query_routes.py  # Speed engine + SSE streaming
│   │   │   ├── query_routes.py       # Standard generate/execute/insights
│   │   │   ├── database_routes.py    # Connection management + schema
│   │   │   ├── auth_routes.py        # Registration + login + refresh
│   │   │   ├── history_routes.py     # Query audit trail
│   │   │   └── export_routes.py      # CSV / Excel / PDF export
│   │   ├── services/
│   │   │   ├── ai/
│   │   │   │   ├── llm_service.py         # Multi-provider LLM client
│   │   │   │   ├── sql_generator.py       # NL→SQL with self-correction
│   │   │   │   ├── prompt_builder.py      # Template loader + context injector
│   │   │   │   ├── query_enhancer.py      # Intent expansion + hint injection
│   │   │   │   ├── schema_context_builder.py # Schema → AI-readable text
│   │   │   │   ├── column_validator.py    # Fuzzy column name correction
│   │   │   │   ├── performance_cache.py   # Multi-level TTL cache
│   │   │   │   ├── query_complexity.py    # EASY/MEDIUM/HARD classifier
│   │   │   │   └── analytics_insight_generator.py # Stats + trend detection
│   │   │   └── database/
│   │   │       ├── connection_service.py  # Engine factory + pooling
│   │   │       ├── schema_service.py      # Schema inspection + AI formatting
│   │   │       └── query_executor.py      # Secure execution + row serialization
│   │   ├── prompts/                 # LLM prompt templates (editable)
│   │   │   ├── sql_prompt.txt        # Master SQL generation prompt (tiered)
│   │   │   ├── explanation_prompt.txt
│   │   │   ├── analytics_prompt.txt
│   │   │   └── chart_prompt.txt
│   │   ├── core/                    # Config, logging, exceptions, constants
│   │   └── db/                      # SQLAlchemy models, migrations, session
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── requirements.txt
└── frontend/
    ├── app.py                       # Streamlit entry point + global CSS
    ├── pages/
    │   ├── dashboard.py              # Main query interface
    │   ├── settings.py               # LLM model, theme, preferences
    │   ├── query_history.py          # Audit trail + replay
    │   ├── past_connections.py       # Saved database connections
    │   └── profile.py                # User profile management
    ├── services/                    # API client wrappers
    ├── components/                  # Reusable Streamlit UI components
    └── utils/                       # Session, connection, settings managers
```

---

## Running Tests

```bash
cd backend
pytest --cov=app --cov-report=term-missing
```

Tests are located in `backend/app/tests/`. The test suite uses SQLite for the internal database and mocks all LLM calls.

---

## Configuration Reference

All configuration is managed via environment variables in `backend/.env`. See [`backend/.env.example`](backend/.env.example) for the full reference.

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | `DataPilot AI` | Application display name |
| `API_PREFIX` | `/api/v1` | API route prefix |
| `LLM_PROVIDER` | `openai` | Active LLM provider |
| `QUERY_TIMEOUT_SECONDS` | `30` | Per-query execution timeout |
| `MAX_RESULT_ROWS` | `10000` | Maximum rows returned per query |
| `MAX_EXPORT_ROWS` | `50000` | Maximum rows in export files |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` | Access token lifetime (7 days default) |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `INTERNAL_DB_URL` | `sqlite:///./sql_tool.db` | Internal state database |

---

## Contributing

1. Fork the repository and create a feature branch
2. Follow the existing code style (Black + Ruff for formatting)
3. Add or update tests for any changed behavior
4. Run `pytest` and ensure all tests pass before submitting a PR

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">Built with ❤️ using FastAPI · LangGraph · Streamlit</p>