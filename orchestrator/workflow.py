from langgraph.graph import StateGraph, END

from state import AgentState

from agents.retriever import retriever_node
from agents.planner   import planner_node
from agents.editor    import editor_node
from agents.validator import validator_node
from agents.tester    import tester_node

from executor.runner import executor_node

from github.commit_agent import commit_agent_node
from github.push_agent   import push_agent_node
from github.pr_agent     import pr_agent_node

from utils.logger import get_logger

logger = get_logger("workflow")

MAX_RETRIES = 2


# ------------------------------------------------
# ROUTING FUNCTIONS  (must be pure — no state mutation)
# ------------------------------------------------
def route_after_editor(state):
    plan = state.get("plan", {}) or {}
    if plan.get("mode") == "explain_only":
        logger.info("Explain-only task complete — ending workflow")
        return END
    return "validator"


def route_after_execution(state):

    execution_error = (state.get("execution_error") or "").lower()

    if "no retrievable functions for task" in execution_error:
        logger.warning("No applicable functions retrieved for task — ending workflow")
        return END

    if "no edits were applied by editor" in execution_error:
        logger.warning("Editor produced no changes — ending workflow")
        return END

    if "no edited files produced" in execution_error:
        logger.warning("No edited files produced — ending workflow")
        return END

    if state.get("execution_success"):
        logger.info("Execution succeeded — routing to tester")
        return "tester"

    retry = state.get("retry_count", 0)

    if retry < MAX_RETRIES:
        logger.info("Execution failed — retry %d/%d", retry + 1, MAX_RETRIES)
        return "retry"

    logger.warning("Max retries reached — ending workflow")
    return END


def route_after_tests(state):

    if state.get("tests_passed", True):
        logger.info("Tests passed — routing to commit")
        return "commit"

    retry = state.get("retry_count", 0)

    if retry < MAX_RETRIES:
        logger.info("Tests failed — retry %d/%d", retry + 1, MAX_RETRIES)
        return "retry"

    logger.warning("Tests failed after max retries — committing anyway")
    return "commit"


# ------------------------------------------------
# BUILD WORKFLOW
# ------------------------------------------------
def build_workflow():

    workflow = StateGraph(AgentState)

    # Retry node — increments counter so routing functions stay pure
    def retry_node(state):
        state["retry_count"] = state.get("retry_count", 0) + 1
        return state

    # Register nodes
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("planner",   planner_node)
    workflow.add_node("editor",    editor_node)
    workflow.add_node("validator", validator_node)
    workflow.add_node("executor",  executor_node)
    workflow.add_node("tester",    tester_node)
    workflow.add_node("retry",     retry_node)

    workflow.add_node("commit", commit_agent_node)
    workflow.add_node("push",   push_agent_node)
    workflow.add_node("pr",     pr_agent_node)

    # Entry point
    workflow.set_entry_point("retriever")

    # Main pipeline
    workflow.add_edge("retriever", "planner")
    workflow.add_edge("planner",   "editor")
    workflow.add_conditional_edges(
        "editor",
        route_after_editor,
        {
            "validator": "validator",
            END: END,
        }
    )
    workflow.add_edge("validator", "executor")

    # Self-repair loop after executor
    workflow.add_conditional_edges(
        "executor",
        route_after_execution,
        {
            "tester": "tester",
            "retry":  "retry",
            END:      END
        }
    )

    # Test gate — retry on failure or proceed to commit
    workflow.add_conditional_edges(
        "tester",
        route_after_tests,
        {
            "commit": "commit",
            "retry":  "retry"
        }
    )

    # Retry loops back to planner (with diagnosis in state)
    workflow.add_edge("retry", "planner")

    # GitHub automation
    workflow.add_edge("commit", "push")
    workflow.add_edge("push",   "pr")
    workflow.add_edge("pr",     END)

    return workflow.compile()
