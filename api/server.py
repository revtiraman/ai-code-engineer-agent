"""
FastAPI backend for the AI Engineer pipeline.

Start with:
    uvicorn api.server:app --reload --port 8000
"""

import os
import sys
import uuid
import queue
import logging
import threading
import subprocess
import traceback as tb
from typing import Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── add project root to Python path ───────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── app ────────────────────────────────────────────────────
app = FastAPI(title="AI Engineer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── in-memory run store ────────────────────────────────────
runs: Dict[str, Any] = {}


# ── request / response models ──────────────────────────────
class RunRequest(BaseModel):
    repo_url:    str
    user_prompt: str


class RunResponse(BaseModel):
    run_id: str


# ── custom logging handler ─────────────────────────────────
class QueueLogHandler(logging.Handler):
    """Intercepts all log records and pushes them into a sync queue."""

    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue
        self.setFormatter(logging.Formatter(
            fmt="%(asctime)s  [%(name)-20s]  %(levelname)-8s  %(message)s",
            datefmt="%H:%M:%S"
        ))

    def emit(self, record):
        try:
            self.log_queue.put_nowait(self.format(record))
        except Exception:
            pass


# ── pipeline runner (runs in a background thread) ──────────
def _run_pipeline(run_id: str, repo_url: str, user_prompt: str):
    log_queue = runs[run_id]["log_queue"]
    handler   = QueueLogHandler(log_queue)

    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    try:
        from github.repo_loader import repo_loader_node
        from rag.repo_indexer import repo_indexer_node
        from orchestrator.workflow import build_workflow

        state = {
            "repo_url":    repo_url,
            "user_prompt": user_prompt,
            "retry_count": 0,
            "has_error":   False,
        }

        state = repo_loader_node(state)
        state = repo_indexer_node(state)

        workflow = build_workflow()
        result   = workflow.invoke(state)

        execution_success = result.get("execution_success")
        tests_passed = result.get("tests_passed")
        terminal_error = result.get("execution_error")

        final_status = "completed"
        if terminal_error or execution_success is False:
            final_status = "error"
        elif tests_passed is False and not result.get("pr_url"):
            final_status = "error"

        runs[run_id]["status"] = final_status
        runs[run_id]["result"] = {
            "edited_files":      result.get("edited_files", []),
            "execution_success": result.get("execution_success"),
            "execution_error":   result.get("execution_error"),
            "debug_diagnosis":   result.get("debug_diagnosis"),
            "test_results":      result.get("test_results", {}),
            "tests_passed":      result.get("tests_passed"),
            "pr_url":            result.get("pr_url"),
            "branch_name":       result.get("branch_name"),
            "plan":              result.get("plan", {}),
            "explanation_file":  result.get("explanation_file"),
            "explanation_preview": result.get("explanation_preview"),
        }

    except Exception as e:

        runs[run_id]["status"] = "error"
        runs[run_id]["result"] = {
            "error":     str(e),
            "traceback": tb.format_exc()
        }
        log_queue.put_nowait(f"FATAL ERROR: {e}")

    finally:

        root.removeHandler(handler)
        log_queue.put_nowait("__DONE__")


# ── REST endpoints ─────────────────────────────────────────

@app.post("/api/run", response_model=RunResponse)
def start_run(req: RunRequest):
    """Kick off a new pipeline run. Returns a run_id to track progress."""

    run_id = str(uuid.uuid4())

    runs[run_id] = {
        "status":    "running",
        "log_queue": queue.Queue(),
        "result":    None,
    }

    t = threading.Thread(
        target=_run_pipeline,
        args=(run_id, req.repo_url, req.user_prompt),
        daemon=True,
    )
    t.start()

    return {"run_id": run_id}


@app.get("/api/run/{run_id}")
def get_run(run_id: str):
    """Poll run status and result."""

    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found")

    run = runs[run_id]
    return {"status": run["status"], "result": run["result"]}


@app.get("/api/diff/{run_id}")
def get_diff(run_id: str):
    """Return git diff stat for the last commit in the workspace repo."""

    repo_path = "./workspace/repo"

    try:
        # Full diff (patch) for the last commit
        patch = subprocess.run(
            ["git", "-C", repo_path, "diff", "HEAD~1", "HEAD"],
            capture_output=True, text=True, timeout=15
        ).stdout

        # Summary stat
        stat = subprocess.run(
            ["git", "-C", repo_path, "diff", "HEAD~1", "HEAD", "--stat"],
            capture_output=True, text=True, timeout=15
        ).stdout

        return {"stat": stat.strip(), "patch": patch.strip()}

    except Exception as e:
        return {"stat": "", "patch": f"Diff unavailable: {e}"}


@app.websocket("/api/ws/{run_id}")
async def websocket_logs(websocket: WebSocket, run_id: str):
    """Stream live logs to the frontend over WebSocket."""
    import asyncio

    if run_id not in runs:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    log_queue = runs[run_id]["log_queue"]

    try:
        while True:
            try:
                msg = log_queue.get_nowait()
            except queue.Empty:
                # No log yet — send a keep-alive ping and yield control
                await websocket.send_json({"type": "ping"})
                await asyncio.sleep(0.3)
                continue

            if msg == "__DONE__":
                await websocket.send_json({
                    "type":   "done",
                    "status": runs[run_id]["status"],
                    "result": runs[run_id]["result"],
                })
                break

            await websocket.send_json({"type": "log", "message": msg})

    except WebSocketDisconnect:
        pass
    except Exception:
        pass


@app.get("/api/health")
def health():
    return {"status": "ok"}
