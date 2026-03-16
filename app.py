import io
import logging
import os
import traceback
from contextlib import redirect_stdout
from pathlib import Path

import streamlit as st


def _find_architecture_image() -> Path | None:
    """Find an architecture diagram image in common repository locations."""
    candidates = [
        Path("assets/architecture.png"),
        Path("assets/architecture.jpg"),
        Path("assets/architecture.jpeg"),
        Path("assets/architecture.webp"),
        Path("assets/architecture.svg"),
        Path("assets/architecture-diagram.png"),
        Path("docs/architecture.png"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _apply_streamlit_secrets_to_env() -> None:
    """Expose Streamlit secrets as environment variables for existing code paths."""
    try:
        for key, value in st.secrets.items():
            os.environ[str(key)] = str(value)
    except Exception:
        # Local runs may not have Streamlit secrets configured.
        pass


def _get_llm_provider() -> str:
    return os.getenv("LLM_PROVIDER", "").strip().lower()


class _BufferLogHandler(logging.Handler):
    def __init__(self, sink):
        super().__init__()
        self.sink = sink
        self.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s  [%(name)-20s]  %(levelname)-8s  %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    def emit(self, record):
        try:
            self.sink.append(self.format(record))
        except Exception:
            pass


st.set_page_config(page_title="AI Code Engineer Agent", page_icon="🤖", layout="wide")
_apply_streamlit_secrets_to_env()

st.title("🤖 AI Code Engineer Agent")
st.caption("Autonomous repository modification pipeline")

with st.sidebar:
    st.header("Configuration")
    provider_label = _get_llm_provider() or "auto"
    openrouter_tokens = os.getenv("OPENROUTER_MAX_TOKENS", "96")
    st.caption(f"Provider: {provider_label} | OpenRouter max tokens: {openrouter_tokens}")

    architecture_image = _find_architecture_image()
    if architecture_image:
        st.image(str(architecture_image), caption="System architecture", use_container_width=True)
    else:
        st.caption("Add architecture image at assets/architecture.png (or .jpg/.jpeg/.webp/.svg) to display it here.")

    repo_url = st.text_input(
        "Repository URL",
        value="https://github.com/revtiraman/fastapi",
        help="Public GitHub repository URL",
    )
    user_prompt = st.text_area(
        "Task / Prompt",
        value="Add logging to API routes",
        height=120,
    )
    run_clicked = st.button("Run Pipeline", type="primary", use_container_width=True)

st.markdown("---")
log_container = st.container()
result_container = st.container()

if run_clicked:
    if not repo_url.strip() or not user_prompt.strip():
        st.error("Please provide both repository URL and prompt.")
        st.stop()

    logs = []
    stdout_buffer = io.StringIO()

    root_logger = logging.getLogger()
    handler = _BufferLogHandler(logs)
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    with st.spinner("Running pipeline... this can take a few minutes"):
        try:
            provider = _get_llm_provider()
            has_bedrock = bool(os.getenv("AWS_BEARER_TOKEN_BEDROCK", "").strip())
            has_openrouter = bool(os.getenv("OPENROUTER_API_KEY", "").strip() or os.getenv("OPENROUTER_API_KEYS", "").strip())
            has_groq = bool(os.getenv("GROQ_API_KEY", "").strip())

            # Respect strict provider mode when configured.
            if provider == "openrouter" and not has_openrouter:
                st.error(
                    "LLM_PROVIDER is set to openrouter, but OPENROUTER_API_KEY/OPENROUTER_API_KEYS is missing in Streamlit Secrets."
                )
                st.stop()

            if provider == "bedrock" and not has_bedrock:
                st.error(
                    "LLM_PROVIDER is set to bedrock, but AWS_BEARER_TOKEN_BEDROCK is missing in Streamlit Secrets."
                )
                st.stop()

            if provider == "groq" and not has_groq:
                st.error(
                    "LLM_PROVIDER is set to groq, but GROQ_API_KEY is missing in Streamlit Secrets."
                )
                st.stop()

            if not provider and not (has_bedrock or has_openrouter or has_groq):
                st.error(
                    "No LLM credentials configured. Add one of these in Streamlit Secrets: "
                    "AWS_BEARER_TOKEN_BEDROCK, OPENROUTER_API_KEY/OPENROUTER_API_KEYS, or GROQ_API_KEY"
                )
                st.stop()

            from github.repo_loader import repo_loader_node
            from rag.repo_indexer import repo_indexer_node
            from orchestrator.workflow import build_workflow

            state = {
                "repo_url": repo_url.strip(),
                "user_prompt": user_prompt.strip(),
                "retry_count": 0,
                "has_error": False,
            }

            with redirect_stdout(stdout_buffer):
                state = repo_loader_node(state)
                state = repo_indexer_node(state)
                workflow = build_workflow()
                result = workflow.invoke(state)

            stdout_text = stdout_buffer.getvalue().strip()
            if stdout_text:
                logs.extend(stdout_text.splitlines())

            with log_container:
                st.subheader("Live Logs")
                st.code("\n".join(logs) if logs else "No logs captured.", language="text")

            with result_container:
                st.subheader("Run Result")
                col1, col2, col3 = st.columns(3)
                col1.metric("Execution Success", str(result.get("execution_success")))
                col2.metric("Tests Passed", str(result.get("tests_passed")))
                col3.metric("Edited Files", len(result.get("edited_files", [])))

                if result.get("execution_error"):
                    st.error(result.get("execution_error"))

                if result.get("debug_diagnosis"):
                    st.warning(result.get("debug_diagnosis"))

                explanation_file = result.get("explanation_file")
                if explanation_file:
                    st.success(f"Explanation generated: {explanation_file}")
                    preview = result.get("explanation_preview")
                    if preview:
                        st.text_area("Explanation preview", preview, height=220)

                if result.get("edited_files"):
                    st.markdown("#### Edited Files")
                    for file_path in result.get("edited_files", []):
                        st.write(f"- {file_path}")

                if result.get("test_results"):
                    st.markdown("#### Test Results")
                    st.json(result.get("test_results"))

                if result.get("branch_name"):
                    st.info(f"Branch: {result.get('branch_name')}")

                if result.get("pr_url"):
                    st.success(f"PR: {result.get('pr_url')}")

                with st.expander("Raw Result JSON"):
                    st.json(result)

        except Exception:
            logs.extend(stdout_buffer.getvalue().splitlines())
            with log_container:
                st.subheader("Live Logs")
                st.code("\n".join(logs) if logs else "No logs captured.", language="text")

            with result_container:
                st.error("Pipeline failed with an exception")
                st.code(traceback.format_exc(), language="text")
        finally:
            root_logger.removeHandler(handler)
