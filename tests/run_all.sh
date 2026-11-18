#!/usr/bin/env bash
# Runs every test. Exit code is non-zero if any test fails.   bash tests/run_all.sh
set -u
cd "$(dirname "$0")/.."
mkdir -p tests/.work
fail=0
for t in test_gates test_llm_budget test_download_limits test_feedback test_gigs test_roles test_pipeline test_remote test_role_focus test_auth test_refresher test_deploy test_attacks test_careers test_profiles; do
  [ -f "tests/$t.py" ] || continue
  if python tests/$t.py > "tests/.work/$t.log" 2>&1; then
    echo "PASS  $t  ($(grep -c '^PASS' tests/.work/$t.log) checks)"
  else
    echo "FAIL  $t — see tests/.work/$t.log"; grep '^FAIL' "tests/.work/$t.log" | head -5
    grep -q '^FAIL' "tests/.work/$t.log" || tail -25 "tests/.work/$t.log"   # crashed: show the traceback
    fail=1
  fi
done
python eval/verify_metrics.py 2>/dev/null | sed 's/^/      metric check: /' || true
exit $fail
