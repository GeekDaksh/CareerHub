"""Login for the public Render link: fails closed, rate-limited, signed cookie.  python tests/test_auth.py"""
import importlib
import json
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "tests", ".work", "auth")
shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(os.path.join(WORK, "gigs"))
json.dump({"gigs": []}, open(os.path.join(WORK, "gigs", "gigs.json"), "w"))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "app"))
from fastapi.testclient import TestClient  # noqa: E402

FAILS = []
H = {"X-Career-Hub": "1"}


def chk(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c:
        FAILS.append(m)


def boot(**env):
    for k in ("APP_PASSWORD", "SESSION_SECRET", "RENDER", "HF_TOKEN"):
        os.environ.pop(k, None)
    os.environ.update(DATA_DIR=WORK, **env)
    import server
    importlib.reload(server)
    return server, TestClient(server.app, base_url="https://testserver", follow_redirects=False)


# ---------------------------------------------------------------- fail closed on a public host
srv, c = boot(RENDER="true")
chk(c.get("/api/data").status_code == 503 and c.get("/").status_code == 503,
    "public host with NO password: the app refuses to show anything (fails closed)")
chk(c.get("/healthz").status_code == 200, "health check still answers, so Render knows the server is up")
srv, c = boot(RENDER="true", APP_PASSWORD="short", SESSION_SECRET="x" * 32)
chk(c.get("/api/data").status_code == 503, "a weak password (under 10 characters) is refused")
srv, c = boot(RENDER="true", APP_PASSWORD="a-long-password-1", SESSION_SECRET="")
chk(c.get("/api/data").status_code == 503, "a missing session secret is refused")

# ---------------------------------------------------------------- normal login
PW = "correct-horse-battery"
srv, c = boot(RENDER="true", APP_PASSWORD=PW, SESSION_SECRET="s" * 40)
r = c.get("/")
chk(r.status_code == 303 and r.headers["location"] == "/login", "not signed in: the page sends you to /login")
chk(c.get("/api/data").status_code == 401, "not signed in: data API answers 401")
chk(c.post("/api/track", json={"key": "gig:x", "status": "saved"}, headers=H).status_code == 401,
    "not signed in: tracker can't be changed")
chk(c.get("/static/index.html").status_code in (401, 303, 404), "not signed in: the page file isn't served")
chk("password" in c.get("/login").text, "the login page loads")

r = c.post("/login", data={"password": "wrong-password"})
chk(r.status_code == 401 and "ch_session" not in r.cookies, "wrong password: refused, no cookie")
r = c.post("/login", data={"password": PW}, headers={"Origin": "https://evil.example"})
chk(r.status_code == 403, "login form posted from another website is refused")

r = c.post("/login", data={"password": PW})
setc = r.headers.get("set-cookie", "").lower()
chk(r.status_code == 303 and "ch_session=" in setc, "right password: signed in")
chk("httponly" in setc and "samesite=strict" in setc and "secure" in setc,
    "cookie is HttpOnly + SameSite=Strict + Secure (scripts and other sites can't use it)")
chk(c.get("/api/data").status_code == 200, "signed in: data loads")
chk(c.post("/api/track", json={"key": "gig:x", "status": "saved"}, headers=H).status_code == 200,
    "signed in: tracker works (the CSRF header rule still applies)")
chk(c.post("/api/track", json={"key": "gig:x", "status": "saved"}).status_code == 403,
    "signed in but no app header: still refused (cookie alone is not enough)")

good = c.cookies.get("ch_session")
u, exp, sig = good.split(".")
for bad, what in [(f"{u}.{int(exp) + 999999}.{sig}", "a longer expiry with the old signature"),
                  (f"{u}.{int(time.time()) - 10}.{srv._sign(u, int(time.time()) - 10)}", "an expired cookie"),
                  ("garbage", "garbage"), (f"{u}.{exp}.{'0' * 64}", "a forged signature"),
                  (f"{exp}.{sig}", "an old-format cookie (no profile)"), (f"aruja.{exp}.{sig}", "another profile's name on Daksh's signature")]:
    c2 = TestClient(srv.app, base_url="https://testserver", follow_redirects=False)
    c2.cookies.set("ch_session", bad, domain="testserver")
    chk(c2.get("/api/data").status_code == 401, f"cookie attack refused: {what}")

r = c.get("/logout")
chk(r.status_code == 303 and "ch_session=" in r.headers.get("set-cookie", "") and "max-age=0" in r.headers.get("set-cookie", "").lower(),
    "sign out clears the cookie")

# ---------------------------------------------------------------- guessing is slowed down
srv, c = boot(RENDER="true", APP_PASSWORD=PW, SESSION_SECRET="s" * 40)
codes = [c.post("/login", data={"password": f"guess{i}"}).status_code for i in range(7)]
chk(codes[:5] == [401] * 5 and codes[5:] == [429, 429], f"6th wrong guess within 15 min is blocked ({codes})")
chk(c.post("/login", data={"password": PW}).status_code == 429, "while blocked, even the right password waits (no oracle)")
srv._fails.clear()
for i in range(30):
    srv._fails.append((time.time(), f"10.0.0.{i}"))
chk(c.post("/login", data={"password": "x"}, headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 429,
    "30 wrong guesses from many addresses lock the login for everyone (fake IP headers don't help)")
r = c.post("/login", content=b"password=" + b"a" * 10000, headers={"Content-Type": "application/x-www-form-urlencoded"})
chk(r.status_code == 413, "a huge login form is refused")

# ---------------------------------------------------------------- local / tests: no password needed
srv, c = boot()
chk(c.get("/api/data").status_code == 200, "on your own computer (not a public host) no login is needed")

print("\nFAILURES:", FAILS)
sys.exit(1 if FAILS else 0)
