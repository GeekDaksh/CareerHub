"""Deploy: the private data store is created/checked; the app itself is a Render blueprint.  python tests/test_deploy.py"""
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FAILS = []


def chk(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c:
        FAILS.append(m)


calls = []
PRIVATE = {"v": True}


class FakeApi:
    def __init__(self, token=None): self.token = token
    def whoami(self): return {"name": "dakshpatil"}
    def create_repo(self, rid, **k): calls.append(("create", rid, k.get("repo_type"), k.get("private")))
    def update_repo_settings(self, rid, **k): calls.append(("private", rid))
    def repo_info(self, rid, repo_type=None): return types.SimpleNamespace(private=PRIVATE["v"])


import huggingface_hub  # noqa: E402
huggingface_hub.HfApi = FakeApi
os.environ["HF_TOKEN"] = "hf_x"
import importlib.util  # noqa: E402
spec = importlib.util.spec_from_file_location("dep", os.path.join(ROOT, "deploy/deploy_space.py"))
dep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dep)
dep.main()
chk(("create", "dakshpatil/career-hub-data", "dataset", True) in calls and not any(c[2] == "space" for c in calls if c[0] == "create"),
    "deploy: creates only the PRIVATE dataset (no paid HF Space)")
PRIVATE["v"] = False
try:
    dep.main()
    chk(False, "deploy: stops when the dataset is public")
except SystemExit:
    chk(True, "deploy: stops when the dataset is public")

import yaml  # noqa: E402
bp = yaml.safe_load(open(os.path.join(ROOT, "render.yaml")))
svc = bp["services"][0]
env = {e["key"]: e for e in svc["envVars"]}
chk(svc["plan"] == "free" and svc["autoDeploy"] is True and svc["type"] == "web", "render.yaml: free web service, redeploys on push")
chk(env["APP_PASSWORD"].get("sync") is False and env["HF_TOKEN"].get("sync") is False and "value" not in env["HF_TOKEN"],
    "render.yaml: password and token are typed in Render, never stored in the repo")
chk(env["SESSION_SECRET"].get("generateValue") is True, "render.yaml: session secret is random, made by Render")
chk("uvicorn server:app" in svc["startCommand"] and "PYTHONPATH=.." in svc["startCommand"] and svc["healthCheckPath"] == "/healthz",
    "render.yaml: starts the same server the tests use, with a health check")
print("\nFAILURES:", FAILS)
sys.exit(1 if FAILS else 0)
