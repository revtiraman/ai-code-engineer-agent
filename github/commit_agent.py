import subprocess


def commit_agent_node(state):

    print("\nCommit Agent Running...\n")

    repo_path = state["repo_path"]

    try:

        subprocess.run(
            ["git", "-C", repo_path, "add", "."],
            check=True
        )

        result = subprocess.run(
            ["git", "-C", repo_path, "status", "--porcelain"],
            capture_output=True,
            text=True
        )

        if result.stdout.strip() == "":
            print("No changes to commit")
            return state

        subprocess.run(
            [
                "git",
                "-C",
                repo_path,
                "commit",
                "-m",
                "AI Agent: Automated code modification"
            ],
            check=True
        )

        print("Commit created")

    except Exception as e:

        print("Commit error:", e)

    return state