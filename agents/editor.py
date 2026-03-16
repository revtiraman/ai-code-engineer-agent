import ast
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.model_router import coder_model
from utils.logger import get_logger

logger = get_logger("editor")

EDITOR_MAX_WORKERS = int(os.getenv("EDITOR_MAX_WORKERS", "1"))

_LOCK_REGISTRY = {}
_LOCK_REGISTRY_GUARD = threading.Lock()


def _get_file_lock(file_path):
    with _LOCK_REGISTRY_GUARD:
        if file_path not in _LOCK_REGISTRY:
            _LOCK_REGISTRY[file_path] = threading.Lock()
        return _LOCK_REGISTRY[file_path]


def clean_code_output(text):

    text = text.strip()

    if "```" in text:
        parts = text.split("```")
        for p in parts:
            if "def " in p or "class " in p:
                return p.strip()

    return text


def _extract_target_file(user_prompt: str) -> str:
    match = re.search(r"([A-Za-z0-9_./-]+\.py)", user_prompt or "")
    return match.group(1) if match else ""


def _resolve_target_file(repo_path: str, target_file: str) -> str:
    if not target_file:
        return ""

    rel = target_file.strip().lstrip("./")
    abs_path = os.path.join(repo_path, rel)
    if os.path.exists(abs_path):
        return abs_path

    basename = os.path.basename(rel)
    for root, _, files in os.walk(repo_path):
        if basename in files:
            return os.path.join(root, basename)

    return ""


def _generate_explanation_markdown(task: str, target_file: str, source_code: str) -> str:
    prompt = f"""You are an expert Python educator.

Create a thorough line-by-line explanation for the given Python file.

TASK:
{task}

TARGET FILE:
{target_file}

RULES:
- Return valid Markdown only.
- Explain code in execution order and mention important line ranges.
- Include concise sections: Overview, Line-by-line Notes, Key Concepts, Caveats.
- If exact one-line mapping is too noisy, group into small contiguous line ranges.

CODE:
{source_code[:12000]}
"""
    return coder_model(prompt).strip()


def replace_function(file_path, func_name, new_code):

    try:

        # Validate generated snippet before touching disk.
        try:
            generated_tree = ast.parse(new_code)
            if not any(isinstance(n, ast.FunctionDef) for n in generated_tree.body):
                logger.error("Generated code for %s::%s is not a function", file_path, func_name)
                return False
        except Exception as exc:
            logger.error("Generated code parse error for %s::%s: %s", file_path, func_name, exc)
            return False

        lock = _get_file_lock(file_path)
        with lock:

            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()

            # If file is already broken, don't write blind edits on top of it.
            tree = ast.parse(source)
            lines = source.splitlines()

            for node in ast.walk(tree):

                if isinstance(node, ast.FunctionDef) and node.name == func_name:

                    start = node.lineno - 1
                    end   = node.end_lineno

                    updated_lines = (
                        lines[:start]
                        + new_code.splitlines()
                        + lines[end:]
                    )
                    updated_source = "\n".join(updated_lines)

                    # Guardrail: only persist edits that keep file syntax valid.
                    ast.parse(updated_source)

                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(updated_source)

                    return True

            logger.warning("Function %s not found in %s", func_name, file_path)
            return False

    except Exception as e:

        logger.error("Patch error in %s: %s", file_path, e)
        return False


def edit_single_block(block, task, debug_diagnosis):
    """Edit one retrieved block — called concurrently in a thread."""

    file_path = block["file"]
    code      = block["code"]
    func_name = block.get("name")
    truncated = code[:1500]

    if not os.path.exists(file_path):
        logger.warning("Skipping missing file during edit: %s", file_path)
        return None

    diagnosis_section = ""
    if debug_diagnosis:
        diagnosis_section = f"""
Previous execution failed with this diagnosis:
{debug_diagnosis}

Use this to guide your fix.
"""

    prompt = f"""You are an expert Python developer.

Modify the following function to accomplish the task.

TASK:
{task}
{diagnosis_section}
CODE:
{truncated}

Return ONLY the updated function. No explanation. No markdown wrapper.
"""

    new_code = coder_model(prompt)
    new_code = clean_code_output(new_code)

    success = replace_function(file_path, func_name, new_code)

    return file_path if success else None


def editor_node(state):

    plan             = state["plan"]
    retrieved_blocks = state.get("retrieved_blocks", [])
    debug_diagnosis  = state.get("debug_diagnosis")

    task = plan.get("task", "")
    mode = plan.get("mode", "edit")

    logger.info("Editor Agent running — task: %s", task)

    if mode == "explain_only":
        repo_path = state.get("repo_path", "")
        target_file = plan.get("target_file") or _extract_target_file(task)
        resolved_target = _resolve_target_file(repo_path, target_file)

        if not resolved_target:
            logger.error("Explain-only task failed: target file not found (%s)", target_file)
            state["execution_success"] = False
            state["execution_error"] = f"Target file not found for explanation: {target_file or 'unknown'}"
            state["edited_files"] = []
            return state

        with open(resolved_target, "r", encoding="utf-8") as f:
            source = f.read()

        explanation = _generate_explanation_markdown(task, resolved_target, source)
        if not explanation:
            logger.error("Explain-only task failed: model returned empty explanation")
            state["execution_success"] = False
            state["execution_error"] = "Failed to generate explanation"
            state["edited_files"] = []
            return state

        output_rel = (plan.get("new_files") or ["explanations/line_by_line_explanation.md"])[0]
        output_abs = os.path.join(repo_path, output_rel)
        os.makedirs(os.path.dirname(output_abs), exist_ok=True)

        with open(output_abs, "w", encoding="utf-8") as f:
            f.write(explanation + "\n")

        state["edited_files"] = [output_abs]
        state["execution_success"] = True
        state["execution_error"] = None
        state["tests_passed"] = True
        state["test_results"] = {}
        state["explanation_file"] = output_abs
        state["explanation_preview"] = explanation[:2000]

        logger.info("Explanation generated: %s", output_abs)
        return state

    if debug_diagnosis:
        logger.info("Incorporating debugger diagnosis into prompts")

    # Keep one edit attempt per (file, function) to reduce conflicting writes.
    seen = set()
    blocks_to_edit = []
    for block in retrieved_blocks:
        if block.get("type") != "function":
            continue
        key = (block.get("file"), block.get("name"))
        if key in seen:
            continue
        seen.add(key)
        blocks_to_edit.append(block)
        if len(blocks_to_edit) >= 5:
            break

    if not blocks_to_edit:
        logger.warning("No function blocks available for editing")
        state["execution_success"] = False
        state["execution_error"] = "No retrievable functions for task"
        state["edited_files"] = []
        return state

    edits_applied = []

    # --------------------------------------------------
    # PARALLEL EDITING: edit multiple blocks concurrently
    # --------------------------------------------------
    with ThreadPoolExecutor(max_workers=min(EDITOR_MAX_WORKERS, len(blocks_to_edit) or 1)) as pool:

        futures = {
            pool.submit(edit_single_block, block, task, debug_diagnosis): block
            for block in blocks_to_edit
        }

        for future in as_completed(futures):
            result = future.result()
            if result:
                edits_applied.append(result)
                logger.info("Edited: %s", result)
            else:
                block = futures[future]
                logger.warning(
                    "Edit failed for %s :: %s", block["file"], block.get("name")
                )

    # De-duplicate while preserving order
    edits_applied = list(dict.fromkeys(edits_applied))

    if not edits_applied:
        logger.warning("No edits applied — marking execution for retry/failure")
        state["execution_success"] = False
        state["execution_error"] = "No edits were applied by editor"

    state["edited_files"] = edits_applied

    logger.info("Edited files: %s", edits_applied)

    return state
