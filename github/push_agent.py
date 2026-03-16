import subprocess
import uuid
import os

GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "revtiraman")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


def _make_authed_url(repo_url: str, token: str, username: str) -> str:
    """Embed token credentials into an HTTPS GitHub URL."""
    bare = repo_url.replace("https://", "").replace(".git", "").rstrip("/")
    return f"https://{username}:{token}@{bare}.git"


def push_agent_node(state):

    print("\nPush Agent Running...\n")

    repo_path = state["repo_path"]
    repo_url = state["repo_url"]
    token = GITHUB_TOKEN
    username = GITHUB_USERNAME

    branch_name = "ai-agent-" + str(uuid.uuid4())[:6]

    # Always set an authenticated remote URL before pushing
    if token:
        authed_url = _make_authed_url(repo_url, token, username)
        subprocess.run(
            ["git", "-C", repo_path, "remote", "set-url", "origin", authed_url],
            check=True
        )

    try:

        subprocess.run(
            ["git", "-C", repo_path, "checkout", "-b", branch_name],
            check=True
        )

        subprocess.run(
            ["git", "-C", repo_path, "push", "-u", "origin", branch_name],
            check=True
        )

        print("Push successful")

        state["branch_name"] = branch_name

    except Exception:

        print("Push failed. Switching to fork...")

        repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        fork_base = f"github.com/{username}/{repo_name}"
        fork_url = f"https://{username}:{token}@{fork_base}.git" if token else f"https://github.com/{username}/{repo_name}.git"

        subprocess.run(
            ["git", "-C", repo_path, "remote", "set-url", "origin", fork_url],
            check=True
        )

        subprocess.run(
            ["git", "-C", repo_path, "push", "-u", "origin", branch_name],
            check=True
        )

        print("Push successful to fork")

        state["branch_name"] = branch_name

    return state