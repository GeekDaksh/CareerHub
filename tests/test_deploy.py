import os as _os, sys as _sys
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
WORKROOT = _os.path.join(ROOT, "tests", ".work")
import os, sys, types
sys.path.insert(0, ROOT)
calls = []
class FakeApi:
    def __init__(self, token=None): self.token = token
    def whoami(self): return {"name": "dakshpatil"}
    def repo_exists(self, rid, repo_type=None): calls.append(("exists", rid)); return EXISTS
    def create_repo(self, rid, **k): calls.append(("create", rid, k.get("repo_type"), k.get("private"), k.get("space_sdk")))
    def update_repo_settings(self, rid, **k): calls.append(("private", rid))
    def repo_info(self, rid, repo_type=None): return types.SimpleNamespace(private=True)
    def add_space_secret(self, rid, k, v): calls.append(("secret", k))
    def add_space_variable(self, rid, k, v): calls.append(("var", k, v))
    def upload_folder(self, folder_path, repo_id, repo_type, commit_message): calls.append(("upload", repo_id, sorted(os.listdir(folder_path)), all(os.path.exists(os.path.join(folder_path, x)) for x in ("static/index.html", "server.py", "common/trust.py", "common/settings.py", "common/apply.py", "common/feedback.py", "config.py"))))
import huggingface_hub; huggingface_hub.HfApi = FakeApi
os.environ.update(HF_TOKEN="hf_x", GITHUB_REPOSITORY="GeekDaksh/career-hub")
import importlib.util
spec = importlib.util.spec_from_file_location("dep", os.path.join(ROOT, "deploy/deploy_space.py")); dep = importlib.util.module_from_spec(spec); spec.loader.exec_module(dep)
EXISTS = False; dep.main()
for c in calls: print(c)
ok = any(c[0]=="create" and c[1]=="dakshpatil/career-hub" and c[2]=="space" and c[3] and c[4]=="docker" for c in calls) \
  and any(c[0]=="create" and c[1]=="dakshpatil/career-hub-data" and c[2]=="dataset" and c[3] for c in calls) \
  and any(c[0]=="upload" and "config.py" in c[2] and "Dockerfile" in c[2] and c[3] for c in calls)
OK1 = ok
print("PASS deploy creates private Space + dataset and uploads server, page, config and shared modules" if ok else "FAIL deploy")
calls.clear(); EXISTS = True; dep.main(ensure_only=True)
OK2 = calls == [("exists", "dakshpatil/career-hub")]
print("PASS --ensure does nothing when Space exists" if OK2 else f"FAIL ensure {calls}")
sys.exit(0 if OK1 and OK2 else 1)
