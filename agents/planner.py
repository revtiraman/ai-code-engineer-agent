import json
import re

from utils.model_router import planner_model
from utils.logger import get_logger

logger = get_logger("planner")


def _extract_target_file(user_prompt: str) -> str:
    match = re.search(r"([A-Za-z0-9_./-]+\.py)", user_prompt)
    return match.group(1) if match else ""


def _is_explanation_task(user_prompt: str) -> bool:
    lowered = user_prompt.lower()
    keywords = ["explain", "line by line", "walk through", "break down"]
    return any(k in lowered for k in keywords)


def clean_json_response(text):

    text = text.strip()

    if "```" in text:
        parts = text.split("```")
        for p in parts:
            if "{" in p:
                text = p
                break

    if text.startswith("json"):
        text = text[4:].strip()

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if match:
        return match.group(0)

    return text


def planner_node(state):

    logger.info("Planner Agent running")

    user_prompt      = state.get("user_prompt", "")
    retrieved_blocks = state.get("retrieved_blocks", [])
    debug_diagnosis  = state.get("debug_diagnosis")

    context = ""

    # Deterministic path for explanation-only requests so we don't hallucinate edit plans.
    if _is_explanation_task(user_prompt):
        target_file = _extract_target_file(user_prompt)
        target_base = (target_file.split("/")[-1] if target_file else "target").replace(".py", "")
        plan = {
            "task": user_prompt,
            "mode": "explain_only",
            "target_file": target_file,
            "files_to_modify": [],
            "functions_to_modify": [],
            "new_files": [f"explanations/{target_base}_line_by_line_explanation.md"],
        }
        state["plan"] = plan
        logger.info("Generated Plan: %s", plan)
        return state

    for block in retrieved_blocks[:5]:

        file_path = block.get("file", "")
        code_type = block.get("type", "")
        name      = block.get("name", "")
        code      = block.get("code", "")
        score     = block.get("score", 0.0)

        context += f"""
FILE: {file_path}  [relevance: {score:.4f}]
TYPE: {code_type}
NAME: {name}

CODE:
{code[:400]}

-------------------------
"""

    diagnosis_section = ""
    if debug_diagnosis:
        diagnosis_section = f"""
--- PREVIOUS FAILURE DIAGNOSIS ---
{debug_diagnosis}
--- END DIAGNOSIS ---

Incorporate this diagnosis when deciding which functions to modify.
"""

    prompt = f"""You are a senior software architect.

A developer wants to perform this task:

{user_prompt}

Below are relevant code blocks from the repository (sorted by relevance score):

{context}
{diagnosis_section}

Create a structured plan for modifying the repository.

Return ONLY valid JSON.

Format:

{{
  "task": "...",
  "files_to_modify": [],
  "functions_to_modify": [],
  "new_files": []
}}
"""

    response = planner_model(prompt)
    cleaned  = clean_json_response(response)

    try:
        plan = json.loads(cleaned)
    except Exception:
        logger.warning("Planner returned invalid JSON — using fallback plan")
        plan = {
            "task": user_prompt,
            "files_to_modify": [],
            "functions_to_modify": [],
            "new_files": []
        }

    state["plan"] = plan

    logger.info("Generated Plan: %s", plan)

    return state
