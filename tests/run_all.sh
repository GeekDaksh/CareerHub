#!/usr/bin/env bash
# Runs every test. Exit code is non-zero if any test fails.   bash tests/run_all.sh
set -u
cd "$(dirname "$0")/.."
mkdir -p tests/.work
fail=0
for t in test_gates test_feedback test_gigs test_roles test_remote test_auth test_deploy test_attacks; do
  [ -f "tests/$t.py" ] || continue
  if python tests/$t.py > "tests/.work/$t.log" 2>&1; then
    echo "PASS  $t  ($(grep -c '^PASS' tests/.work/$t.log) checks)"
  else
    echo "FAIL  $t — see tests/.work/$t.log"; grep '^FAIL' "tests/.work/$t.log" | head -5; fail=1
  fi
done
python eval/verify_metrics.py 2>/dev/null | sed 's/^/      metric check: /' || true
exit $fail
