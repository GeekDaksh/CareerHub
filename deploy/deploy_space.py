"""Create (if needed) the private HF dataset + private HF Space, and push the web app.
Run by GitHub Actions. Needs HF_TOKEN (write).
  python deploy/deploy_space.py            # create if missing + upload app
  python deploy/deploy_space.py --ensure   # only create/upload if the Space doesn't exist yet
"""
import os
import shutil
import sys
import tempfile

from huggingface_hub import HfApi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(ensure_only=False):
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("deploy: HF_TOKEN missing — add it in GitHub → Settings → Secrets → Actions")
        sys.exit(1)
    api = HfApi(token=token)
    user = api.whoami()["name"]
    data_repo = os.environ.get("DATA_REPO") or f"{user}/career-hub-data"
    space = os.environ.get("SPACE_REPO") or f"{user}/career-hub"

    if ensure_only and api.repo_exists(space, repo_type="space"):
        print("deploy: Space exists, nothing to do")
        return
    api.create_repo(data_repo, repo_type="dataset", private=True, exist_ok=True)
    api.create_repo(space, repo_type="space", space_sdk="docker", private=True, exist_ok=True)
    try:   # make sure it stays private even if it was created by hand
        api.update_repo_settings(space, private=True, repo_type="space")
    except Exception:
        pass
    api.add_space_secret(space, "HF_TOKEN", token)
    api.add_space_variable(space, "DATA_REPO", data_repo)
    api.add_space_variable(space, "GITHUB_REPO", os.environ.get("GITHUB_REPOSITORY", ""))

    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(os.path.join(ROOT, "app"), tmp, dirs_exist_ok=True)   # incl. .streamlit/ theme
        shutil.copy(os.path.join(ROOT, "config.py"), tmp)
        api.upload_folder(folder_path=tmp, repo_id=space, repo_type="space", commit_message="deploy from GitHub")

    url = f"https://huggingface.co/spaces/{space}"
    print("deploy: live at", url)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(f"### ✅ Career Hub deployed\nOpen: {url}\n\n(Log in to Hugging Face to see it — it's private.)\n")


if __name__ == "__main__":
    main(ensure_only="--ensure" in sys.argv)
