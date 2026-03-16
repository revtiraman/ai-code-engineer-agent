import requests
import os

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

def fork_repo(repo_full_name):

    print("\nFork Agent Running...\n")

    url = f"https://api.github.com/repos/{repo_full_name}/forks"

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    response = requests.post(url, headers=headers)

    if response.status_code == 202:

        fork_data = response.json()

        print("Fork created:", fork_data["full_name"])

        return fork_data["clone_url"]

    else:

        print("Fork failed:", response.text)

        return None