#!/bin/sh
# Run every suite against iron-ledger.html. Nothing ships without this passing.
#   ./verify.sh          full output
#   ./verify.sh 6        last 6 lines of each suite
set -e

# The suites print ✕, · and friends. A Windows console defaults to cp1252 and
# dies on them, so force UTF-8 for the child processes.
PYTHONUTF8=1; PYTHONIOENCODING=utf-8; export PYTHONUTF8 PYTHONIOENCODING

# Windows ships a "python3" stub that exists on PATH but only advertises the
# Microsoft Store, so probing with `command -v` is not enough — run it.
PY=""
for c in python3 python py; do
  command -v "$c" >/dev/null 2>&1 || continue
  "$c" -c "import sys; assert sys.version_info[0]==3" >/dev/null 2>&1 && { PY="$c"; break; }
done
[ -n "$PY" ] || { echo "no working python 3 found (tried python3, python, py)"; exit 1; }

"$PY" -c "import playwright" 2>/dev/null || {
  echo "Playwright missing. Run:  $PY -m pip install playwright && $PY -m playwright install chromium"; exit 1; }

echo "### testing $(grep -o 'BUILD = \"[^\"]*\"' iron-ledger.html | head -1)  [$PY]"
fail=0
for s in sweep days probe darkcheck audit2 coach meals estmeal touch mobile \
         commit noclaude yourwords firstrun photo2 taborder pwa; do
  echo "=================== $s ==================="
  if [ -n "$1" ]; then out=$("$PY" tests/$s.py 2>&1) || fail=1; echo "$out" | tail -"$1"
  else "$PY" tests/$s.py 2>&1 || fail=1; fi
done
echo "==========================================="
[ "$fail" -eq 0 ] && echo "ALL SUITES PASSED" || { echo "SOME SUITES FAILED"; exit 1; }
