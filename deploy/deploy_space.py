"""Make sure the PRIVATE Hugging Face dataset (where all Career Hub data lives) exists and is private.

The web app itself runs on Render's free plan (render.yaml); Render redeploys it on every push.
Hugging Face started charging for Docker app servers (Spaces) on the free plan in July 2026, so the
app no longer runs there. Run by GitHub Actions. Needs HF_TOKEN (write).
  python deploy/deploy_space.py            # create if missing + verify private
  python deploy/deploy_space.py --ensure   # same; kept so older workflow lines keep working
"""
import os
import sys

from huggingface_hub import HfApi


def main(ensure_only=False):
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("deploy: HF_TOKEN missing — add it in GitHub → Settings → Secrets → Actions")
        sys.exit(1)
    api = HfApi(token=token)
    user = api.whoami()["name"]
    data_repo = os.environ.get("DATA_REPO") or f"{user}/career-hub-data"
    api.create_repo(data_repo, repo_type="dataset", private=True, exist_ok=True)
    # The data holds founders' contacts, your tracker and earnings. Stop everything if it is public.
    try:
        api.update_repo_settings(data_repo, private=True, repo_type="dataset")
    except Exception as e:
        print(f"deploy: could not set {data_repo} private ({e}) — checking its state")
    if not getattr(api.repo_info(data_repo, repo_type="dataset"), "private", False):
        print(f"deploy: STOPPED — dataset {data_repo} is PUBLIC. Make it private on huggingface.co, then re-run.")
        sys.exit(1)
    print(f"deploy: private data store ready: {data_repo}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(f"### ✅ Private data store ready\n`{data_repo}` (private). The web app runs on Render.\n")


if __name__ == "__main__":
    main(ensure_only="--ensure" in sys.argv)
