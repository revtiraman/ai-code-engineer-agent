import os
import subprocess


SKIP_DIRS = [
    ".git",
    "venv",
    "node_modules",
    "tests",
    "docs",
    "docs_src",
    "examples",
    "__pycache__"
]

ALLOWED_EXTENSIONS = [
    ".py",
    ".js",
    ".ts",
    ".java",
    ".go",
    ".rs"
]


GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
CLONE_TIMEOUT_SECONDS = 180
FETCH_TIMEOUT_SECONDS = 180
REV_PARSE_TIMEOUT_SECONDS = 20
RESET_TIMEOUT_SECONDS = 60
GIT_LOCK_FILES = [
    "HEAD.lock",
    "index.lock",
    "packed-refs.lock",
    "shallow.lock",
    "config.lock"
]


def _remove_stale_git_locks(repo_path):
    git_dir = os.path.join(repo_path, ".git")
    removed = False

    for lock_file in GIT_LOCK_FILES:
        lock_path = os.path.join(git_dir, lock_file)
        if os.path.exists(lock_path):
            os.remove(lock_path)
            removed = True

    return removed


def _remove_all_git_locks(repo_path):
    git_dir = os.path.join(repo_path, ".git")
    removed = False

    if not os.path.isdir(git_dir):
        return False

    for root, _, files in os.walk(git_dir):
        for name in files:
            if name.endswith(".lock"):
                lock_path = os.path.join(root, name)
                try:
                    os.remove(lock_path)
                    removed = True
                except OSError:
                    pass

    return removed


def _reset_local_checkout(repo_path):
    """Best-effort cleanup so each run starts from a clean local tree."""
    try:
        subprocess.run(
            ["git", "-C", repo_path, "reset", "--hard", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            env=GIT_ENV,
            timeout=RESET_TIMEOUT_SECONDS
        )
        subprocess.run(
            ["git", "-C", repo_path, "clean", "-fd"],
            check=False,
            capture_output=True,
            text=True,
            env=GIT_ENV,
            timeout=RESET_TIMEOUT_SECONDS
        )
    except Exception:
        # Non-fatal: run can still proceed with best available state.
        pass


def _fetch_with_retries(repo_path, retries=2):
    """Try git fetch multiple times and tolerate timeout on slow remotes."""
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            subprocess.run(
                ["git", "-C", repo_path, "fetch", "--all"],
                check=True,
                capture_output=True,
                text=True,
                env=GIT_ENV,
                timeout=FETCH_TIMEOUT_SECONDS
            )
            return True
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            last_error = stderr or "Git fetch failed"

            if "lock" in stderr and _remove_stale_git_locks(repo_path):
                continue

            if attempt == retries:
                print(f"Git fetch failed after {retries} attempts: {last_error}")
                return False
        except subprocess.TimeoutExpired:
            last_error = "Git fetch timed out"
            if attempt == retries:
                print(f"Git fetch timed out after {retries} attempts. Continuing with local checkout.")
                return False

    print(f"Git fetch skipped due to: {last_error or 'unknown error'}")
    return False


def _normalize_repo_url(url):
    if not url:
        return ""

    normalized = url.strip()
    if normalized.endswith(".git"):
        normalized = normalized[:-4]

    return normalized.rstrip("/")


def _get_origin_url(repo_path):
    result = subprocess.run(
        ["git", "-C", repo_path, "config", "--get", "remote.origin.url"],
        capture_output=True,
        text=True,
        env=GIT_ENV,
        timeout=REV_PARSE_TIMEOUT_SECONDS
    )

    if result.returncode != 0:
        return ""

    return (result.stdout or "").strip()


def repo_loader_node(state):

    repo_url = state["repo_url"]
    repo_id = _normalize_repo_url(repo_url) or repo_url
    repo_path = "./workspace/repo"

    os.makedirs("workspace", exist_ok=True)

    has_git_repo = os.path.isdir(os.path.join(repo_path, ".git"))

    if has_git_repo:
        current_origin = _normalize_repo_url(_get_origin_url(repo_path))
        requested_origin = _normalize_repo_url(repo_url)

        if current_origin and requested_origin and current_origin != requested_origin:
            print(f"Repository URL changed. Re-cloning {repo_url}...")
            subprocess.run(["rm", "-rf", repo_path])
            has_git_repo = False

    if not has_git_repo:

        if os.path.exists(repo_path):
            subprocess.run(["rm", "-rf", repo_path])

        print("Cloning repository...")

        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, repo_path],
            capture_output=True,
            text=True,
            env=GIT_ENV,
            timeout=CLONE_TIMEOUT_SECONDS
        )

        if result.returncode != 0:
            print(result.stderr)
            raise RuntimeError("Git clone failed")

    else:

        print("Repository already exists. Updating repository...")

        # Prevent previous failed edits from poisoning the next run.
        _reset_local_checkout(repo_path)

        fetch_succeeded = _fetch_with_retries(repo_path)

        if not fetch_succeeded:
            print("Proceeding without remote sync; using current local repository state.")

        result = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "origin/HEAD"],
            capture_output=True,
            text=True,
            env=GIT_ENV,
            timeout=REV_PARSE_TIMEOUT_SECONDS
        )

        if result.returncode != 0 or not result.stdout.strip():
            default_branch = "main"
        else:
            default_branch = result.stdout.strip().split("/")[-1]

        candidate_branches = [default_branch, "main", "master"]
        seen = set()
        branch_candidates = []
        for branch in candidate_branches:
            if branch and branch not in seen:
                seen.add(branch)
                branch_candidates.append(branch)

        reset_errors = []
        reset_succeeded = not fetch_succeeded

        for branch in branch_candidates:
            try:
                subprocess.run(
                    ["git", "-C", repo_path, "reset", "--hard", f"origin/{branch}"],
                    check=True,
                    capture_output=True,
                    text=True,
                    env=GIT_ENV,
                    timeout=RESET_TIMEOUT_SECONDS
                )
                reset_succeeded = True
                break
            except subprocess.CalledProcessError as exc:
                stderr = (exc.stderr or "").strip()
                if "lock" in stderr and (_remove_stale_git_locks(repo_path) or _remove_all_git_locks(repo_path)):
                    try:
                        subprocess.run(
                            ["git", "-C", repo_path, "reset", "--hard", f"origin/{branch}"],
                            check=True,
                            capture_output=True,
                            text=True,
                            env=GIT_ENV,
                            timeout=RESET_TIMEOUT_SECONDS
                        )
                        reset_succeeded = True
                        break
                    except subprocess.CalledProcessError as retry_exc:
                        reset_errors.append((retry_exc.stderr or "").strip() or f"reset failed for origin/{branch}")
                elif "ambiguous argument" in stderr or "unknown revision" in stderr:
                    reset_errors.append(stderr or f"origin/{branch} not available")
                else:
                    reset_errors.append(stderr or f"reset failed for origin/{branch}")
            except subprocess.TimeoutExpired:
                reset_errors.append(f"reset timed out for origin/{branch}")

        if not reset_succeeded:
            print("Git reset failed; continuing with local checkout:")
            if reset_errors:
                print(" | ".join(reset_errors))

    files = []

    for root, dirs, file_names in os.walk(repo_path):

        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for file in file_names:

            if any(file.endswith(ext) for ext in ALLOWED_EXTENSIONS):

                files.append(os.path.join(root, file))

    state["repo_path"] = repo_path
    state["repo_id"] = repo_id
    state["files"] = files

    print(f"Found {len(files)} code files")

    return state