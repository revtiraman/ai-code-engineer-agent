import os
import subprocess
import sys

from utils.model_router import debugger_model
from utils.logger import get_logger

logger = get_logger("executor")


def executor_node(state):

    logger.info("Executor Agent running")

    repo_path     = state["repo_path"]
    edited_files  = state.get("edited_files", [])
    abs_repo_path = os.path.abspath(repo_path)

    if not edited_files:
        logger.error("Executor received no edited files; treating run as failed")
        state["execution_success"] = False
        state["execution_error"] = "No edited files produced"
        state["debug_diagnosis"] = "Editor produced no valid edits. Refresh retrieval/index and retry."
        return state

    try:

        result = subprocess.run(
            [sys.executable, "-m", "compileall", "-q", abs_repo_path],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:

            logger.info("Code compiled successfully")

            state["execution_success"] = True
            state["execution_error"]   = None
            state["debug_diagnosis"]   = None

        else:

            error_output = (result.stdout + result.stderr).strip()
            logger.error("Compilation failed:\n%s", error_output)

            # -----------------------------------------------
            # SMARTER SELF-REPAIR: ask debugger LLM to
            # diagnose and suggest a specific fix strategy
            # -----------------------------------------------
            diagnosis = _run_debugger(error_output, edited_files)

            logger.info("Debugger diagnosis:\n%s", diagnosis)

            state["execution_success"] = False
            state["execution_error"]   = error_output
            state["debug_diagnosis"]   = diagnosis

    except Exception as e:

        logger.exception("Execution error: %s", e)

        state["execution_success"] = False
        state["execution_error"]   = str(e)
        state["debug_diagnosis"]   = None

    return state


def _run_debugger(error_output: str, edited_files: list) -> str:
    """Call the LLM debugger to produce a fix strategy from compile errors."""

    files_str = "\n".join(edited_files) if edited_files else "unknown"

    prompt = f"""You are a senior Python debugging engineer.

The following compilation errors occurred after modifying these files:
{files_str}

ERRORS:
{error_output[:3000]}

Diagnose the root cause and provide a concise, actionable fix strategy
that the editor agent should apply on the next retry. Be specific about
which functions need to change and what the fix should be.
"""

    try:
        return debugger_model(prompt)
    except Exception as e:
        return f"Debugger unavailable: {e}"
