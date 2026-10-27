"""Data lives in a PRIVATE Hugging Face dataset, so nothing personal is ever committed to GitHub.

  python -m common.hfstore pull          # download everything into ./data
  python -m common.hfstore push gigs     # upload ./data/gigs
Without HF_TOKEN it works locally only (handy for testing).
"""
import os
import sys

DATA_DIR = os.environ.get("DATA_DIR", "data")


def _token():
    return os.environ.get("HF_TOKEN") or None


def api():
    from huggingface_hub import HfApi
    return HfApi(token=_token())


def username():
    return api().whoami()["name"]


def data_repo():
    return os.environ.get("DATA_REPO") or f"{username()}/career-hub-data"


def ensure_repo():
    if not _token():
        return None
    repo = data_repo()
    api().create_repo(repo, repo_type="dataset", private=True, exist_ok=True)
    return repo


def pull():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not _token():
        print("hfstore: no HF_TOKEN, using local data only")
        return
    from huggingface_hub import snapshot_download
    repo = ensure_repo()
    snapshot_download(repo_id=repo, repo_type="dataset", local_dir=DATA_DIR, token=_token())
    print(f"hfstore: pulled {repo} -> {DATA_DIR}")


def push(subdir, message=None):
    path = os.path.join(DATA_DIR, subdir)
    if not _token():
        print("hfstore: no HF_TOKEN, skipped upload of", subdir)
        return
    if not os.path.isdir(path):
        print("hfstore: nothing to upload in", path)
        return
    repo = ensure_repo()
    api().upload_folder(folder_path=path, path_in_repo=subdir, repo_id=repo, repo_type="dataset",
                        commit_message=message or f"update {subdir}",
                        ignore_patterns=["*.tmp", "**/.cache/**", ".cache/**"])
    print(f"hfstore: pushed {path} -> {repo}/{subdir}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "pull":
        pull()
    elif cmd == "push":
        push(sys.argv[2])
    else:
        print(__doc__)
