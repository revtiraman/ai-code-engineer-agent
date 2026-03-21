# AI Code Engineer Agent

Autonomous multi-agent system that clones a repository, retrieves relevant code, plans and applies edits, validates/executes changes, runs tests, and can create GitHub commits/PRs.

This project includes:
- FastAPI backend with REST + WebSocket log streaming
- LangGraph orchestrated agent workflow
- Streamlit UI for quick deployment/run control
- Optional Next.js frontend in `frontend/`
- Pluggable LLM routing with provider fallback (OpenRouter, Bedrock, Groq)
  
## 🎥 Live Demo (See AI Agent in Action 🚀)

Watch how the system clones, edits, and fixes code automatically:

[![AI Engineer Demo](https://img.youtube.com/vi/O-a4ukwAHfU/0.jpg)](https://www.youtube.com/watch?v=O-a4ukwAHfU)


## What It Does

Given:
- a repository URL
- a natural-language engineering prompt

The system will:
1. Clone or refresh the repo
2. Parse and index code blocks
3. Retrieve top relevant functions/classes
4. Generate an implementation plan
5. Edit target code with LLM-generated patches
6. Validate and compile
7. Retry with debugger-informed fixes when needed
8. Generate/run tests
9. Optionally commit, push, and open a PR

It also supports explain-only tasks (for prompts like "explain X line by line") that generate a markdown explanation artifact instead of code edits.

## Architecture

Core flow:
- API/Streamlit entrypoint initializes run state
- `repo_loader` clones/updates repo
- `repo_indexer` builds embeddings over AST-extracted code blocks
- `retriever` does semantic retrieval + reranking
- `planner` creates structured JSON plan
- `editor` patches functions or writes explanation file
- `validator` / `executor` compiles and diagnoses failures
- `tester` generates/runs pytest tests
- GitHub agents perform commit/push/PR steps

Workflow graph is defined in `orchestrator/workflow.py` using LangGraph conditional routing and retry loops.

## Repository Structure

- `api/server.py`: FastAPI API (`/api/run`, `/api/run/{id}`, `/api/ws/{id}`, `/api/health`)
- `orchestrator/workflow.py`: LangGraph state machine and route logic
- `state.py`: shared typed state object
- `agents/`
  - `retriever.py`: semantic retrieval + reranking
  - `planner.py`: task planning (supports explain-only mode)
  - `editor.py`: code edit generation + apply
  - `validator.py`: validation checks
  - `tester.py`: test generation/execution
- `executor/runner.py`: compile/execute + debugger diagnosis
- `github/`: commit/push/PR automation agents
- `rag/`
  - `repo_indexer.py`: AST extraction/chunking + embedding indexing
  - `vector_store.py`: Chroma persistent store, in-memory fallback
- `utils/model_router.py`: provider routing and key fallback logic
- `app.py`: Streamlit app
- `frontend/`: optional Next.js UI
- `main.py`: local CLI-style orchestrated run

## LLM Provider Behavior

Implemented in `utils/model_router.py`:

- Multi-provider routing with ordered fallback in `auto` mode
- Strict provider mode via `LLM_PROVIDER`:
  - `openrouter`
  - `bedrock`
  - `groq`
  - `auto` (default)
- OpenRouter multi-key fallback via `OPENROUTER_API_KEYS` (comma-separated)

Current recommended mode for this repo setup:
- `LLM_PROVIDER=openrouter`

## Prerequisites

- Python 3.11+ (project has been exercised with Python 3.13 locally)
- Git
- Network access to target repos and selected LLM provider

## Local Setup

### 1) Create and activate virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Configure environment

Create `.env` in repo root.

Minimal OpenRouter-only example:

```dotenv
OPENROUTER_API_KEY=your_primary_openrouter_key
OPENROUTER_API_KEYS=key1,key2,key3
OPENROUTER_MODEL=anthropic/claude-3.7-sonnet
OPENROUTER_SITE_URL=http://localhost:3000
OPENROUTER_APP_NAME="AI Engineer"
OPENROUTER_MAX_TOKENS=256
LLM_PROVIDER=openrouter

GITHUB_TOKEN=your_github_token
GITHUB_USERNAME=your_github_username
```

Optional variables:

```dotenv
# OpenRouter role-specific overrides
OPENROUTER_PLANNER_MODEL=...
OPENROUTER_CODER_MODEL=...
OPENROUTER_DEBUGGER_MODEL=...

# Bedrock
AWS_BEARER_TOKEN_BEDROCK=...
AWS_BEDROCK_OPENAI_API_URL=https://bedrock-runtime.us-east-1.amazonaws.com/openai/v1/chat/completions
BEDROCK_MODEL=...
BEDROCK_PLANNER_MODEL=...
BEDROCK_CODER_MODEL=...
BEDROCK_DEBUGGER_MODEL=...
BEDROCK_MAX_TOKENS=512

# Groq
GROQ_API_KEY=...
GROQ_MAX_RETRIES=4

# Editor/index behavior
EDITOR_MAX_WORKERS=1
FORCE_REINDEX=1
```

## Running the System

### Option A: FastAPI backend

```bash
python -m uvicorn api.server:app --reload --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/api/health
```

Start a run:

```bash
curl -X POST http://127.0.0.1:8000/api/run \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"https://github.com/revtiraman/fastapi","user_prompt":"Add logging to API routes"}'
```

Stream logs via WebSocket:
- Connect to `/api/ws/{run_id}`

### Option B: Streamlit app

```bash
streamlit run app.py
```

In Streamlit UI:
- Set repo URL and prompt in sidebar
- Click "Run Pipeline"
- Watch "Live Logs"
- Review final run metrics/results

### Option C: Script entrypoint

```bash
python main.py
```

## Streamlit Cloud Deployment

Use `.streamlit/secrets.toml` (TOML, not `.env` syntax).

Example:

```toml
OPENROUTER_API_KEY = "your_primary_openrouter_key"
OPENROUTER_API_KEYS = "key1,key2,key3"
OPENROUTER_MODEL = "anthropic/claude-3.7-sonnet"
OPENROUTER_SITE_URL = "http://localhost:3000"
OPENROUTER_APP_NAME = "AI Engineer"
OPENROUTER_MAX_TOKENS = "256"
LLM_PROVIDER = "openrouter"

GITHUB_TOKEN = "your_github_token"
GITHUB_USERNAME = "your_github_username"
```

After updating secrets:
1. Save secrets
2. Reboot app

## API Endpoints

- `POST /api/run`: start pipeline run
- `GET /api/run/{run_id}`: poll run status/result
- `GET /api/diff/{run_id}`: last commit diff stat/patch in workspace repo
- `WS /api/ws/{run_id}`: live logs + terminal done payload
- `GET /api/health`: health check

## Explain-Only Mode

Prompts containing words like "explain", "line by line", "walk through", "break down" trigger explain-only planning.

Result:
- Generates markdown explanation file under `workspace/repo/explanations/...`
- Skips validator/executor/test/commit chain for that run path

## Common Issues and Fixes

### 1) "No LLM credentials configured"
- Ensure Streamlit secrets are valid TOML
- Ensure at least one provider key exists
- Reboot Streamlit app after saving secrets

### 2) OpenRouter 402 insufficient credits
- Keys are valid but account/org has no paid credits
- Add credits or switch to funded keys

### 3) Groq error: `unexpected keyword argument 'proxies'`
- Environment dependency incompatibility (`httpx` vs Groq SDK)
- Use `LLM_PROVIDER=openrouter` or pin compatible versions

### 4) Port already in use for local API
- Kill old process bound to 8000 or run on alternate port (e.g., 8001)

### 5) Missing image in Streamlit sidebar
- Place architecture image in one of:
  - `assets/architecture.png` (recommended)
  - `assets/architecture.jpg`
  - `assets/architecture.jpeg`
  - `assets/architecture.webp`
  - `assets/architecture-diagram.png`
  - `docs/architecture.png`

## Security Notes

- Do not commit real API keys/tokens.
- If keys were exposed, rotate them immediately.
- Prefer using Streamlit Secrets for deployment over hard-coded values.

## Development Notes

- Vector store defaults to persistent Chroma at `vector_db/`
- In environments where Chroma is unavailable, in-memory fallback is used
- Repo indexing is repo-scoped using `repo_id` metadata to avoid cross-repo contamination

## License

No root license file is currently defined in this repository.
Add a `LICENSE` file if you plan to distribute this project.
