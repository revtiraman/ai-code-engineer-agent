# from github.repo_loader import repo_loader_node
# from rag.repo_indexer import repo_indexer_node
# from agents.retriever import retriever_node
# from agents.planner import planner_node
# from agents.editor import editor_node


# state = {
#     "repo_url": "https://github.com/tiangolo/fastapi",
#     "user_prompt": "Add logging to API routes"
# }

# state = repo_loader_node(state)

# state = repo_indexer_node(state)

# state = retriever_node(state)

# state = planner_node(state)

# state = editor_node(state)
from github.repo_loader import repo_loader_node
from rag.repo_indexer import repo_indexer_node
from orchestrator.workflow import build_workflow
from utils.logger import get_logger

logger = get_logger("main")


def main():

    state = {
        "repo_url":    "https://github.com/revtiraman/fastapi",
        "user_prompt": "Add logging to API routes",
        "retry_count": 0,
        "has_error":   False
    }

    # Step 1: clone / update repository
    logger.info("Step 1: Loading repository")
    state = repo_loader_node(state)

    # Step 2: index repository (skips if already indexed)
    logger.info("Step 2: Indexing repository")
    state = repo_indexer_node(state)

    # Step 3: build LangGraph workflow
    logger.info("Step 3: Building workflow")
    workflow = build_workflow()

    # Step 4: run agent pipeline
    logger.info("Step 4: Running agent pipeline")
    result = workflow.invoke(state)

    print("\n" + "=" * 50)
    print("   AI Engineer Execution Result")
    print("=" * 50)

    print("\nEdited Files:")
    for f in result.get("edited_files", []):
        print(f"  {f}")

    print("\nExecution Success:", result.get("execution_success"))

    if result.get("execution_error"):
        print("\nExecution Error:")
        print(result.get("execution_error"))

    if result.get("debug_diagnosis"):
        print("\nDebugger Diagnosis:")
        print(result.get("debug_diagnosis"))

    print("\nTest Results:")
    test_results = result.get("test_results", {})
    if test_results:
        for f, r in test_results.items():
            print(f"  {f}: {r.get('status')}")
    else:
        print("  (none)")

    print("\nTests Passed:", result.get("tests_passed"))

    if result.get("pr_url"):
        print("\nPull Request:")
        print(f"  {result.get('pr_url')}")


if __name__ == "__main__":
    main()
