"""A source that trickles bytes or sends a huge reply can't stall or flood the radar.  python tests/test_download_limits.py"""
import gzip
import http.server
import json
import os
import socketserver
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gigs import sources as S  # noqa: E402

FAILS = []


def chk(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c:
        FAILS.append(m)


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        if self.path.startswith("/gz"):
            body = gzip.compress(json.dumps({"jobs": list(range(5000))}).encode())
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.end_headers()
        try:
            if self.path.startswith("/slow"):          # the real stall: Remotive trickled for minutes
                for _ in range(60):
                    self.wfile.write(b" ")
                    self.wfile.flush()
                    time.sleep(1)
            elif self.path.startswith("/huge"):
                for _ in range(40):
                    self.wfile.write(b" " * 1_000_000)
            else:
                self.wfile.write(json.dumps({"jobs": [1, 2]}).encode())
        except Exception:
            return


srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
srv.daemon_threads = True
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
S.MAX_SECONDS, S.MAX_BYTES = 3, 5_000_000
base = f"http://127.0.0.1:{port}"
chk(S.get(base + "/ok") == {"jobs": [1, 2]}, "normal JSON reply still works")
chk(len(S.get(base + "/gz")["jobs"]) == 5000, "gzip-compressed reply still works")
t = time.time()
try:
    S.get(base + "/slow")
    chk(False, "a trickling server is cut off")
except RuntimeError:
    chk(time.time() - t < 5, f"a server that trickles 1 byte/s is cut off at the time limit ({time.time() - t:.1f}s)")
try:
    S.get(base + "/huge")
    chk(False, "a 40 MB reply is refused")
except RuntimeError as e:
    chk("MB" in str(e), "a 40 MB reply is refused before it fills memory")
print("\nFAILURES:", FAILS)
sys.exit(1 if FAILS else 0)
