from typing import TypedDict, List, Dict, Optional


class AgentState(TypedDict):

    repo_url: str
    repo_path: str
    repo_id: str
    files: List[str]

    user_prompt: str

    retrieved_blocks: List[Dict]

    plan: Dict

    edited_files: List[str]

    validation_results: Dict

    retry_count: int
    has_error: bool

    execution_success: Optional[bool]
    execution_error: Optional[str]

    # Smarter self-repair: debugger diagnosis stored between nodes
    debug_diagnosis: Optional[str]

    # Test generation results
    test_results: Optional[Dict]
    tests_passed: Optional[bool]

    branch_name: Optional[str]
    pr_url: Optional[str]

    relevant_files: Optional[List[str]]
    repo_indexed: Optional[bool]
    indexed_blocks: Optional[int]

    explanation_file: Optional[str]
    explanation_preview: Optional[str]

    branch_name: Optional[str]
    pr_url: Optional[str]