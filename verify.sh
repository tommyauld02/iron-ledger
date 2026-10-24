#!/bin/sh
# Run every suite against mntl-dt.html. Nothing ships without this passing.
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

echo "### testing $(grep -o 'BUILD = \"[^\"]*\"' mntl-dt.html | head -1)  [$PY]"
fail=0
skipped=""
# Each suite writes to a file, never straight to the log. On CI the log is a
# pipe, the Playwright driver shares it through `2>&1`, and it can leave the
# pipe non-blocking: sweep then died printing its ~800 results with
# "BlockingIOError: [Errno 11] write could not complete without blocking",
# every check passed and the run went red (PR #14). A file always blocks.
log=$(mktemp)
trap 'rm -f "$log"' EXIT
for s in sweep days week probe darkcheck coach meals estmeal touch mobile \
         commit noclaude yourwords firstrun photo2 taborder pwa handoff finder relay label hittest share native; do
  echo "=================== $s ==================="
  # `cmd && rc=0 || rc=$?` keeps set -e out of it: a bare `cmd; rc=$?` would
  # abort the whole run on the first failing suite, hiding every later one.
  "$PY" tests/$s.py > "$log" 2>&1 && rc=0 || rc=$?
  if [ -n "$1" ]; then tail -n "$1" "$log"; else cat "$log"; fi
  # 77 is a suite saying it could not run at all, which is not the same as the
  # app being broken. It is still missing coverage, so it is named at the end.
  if [ "$rc" -eq 77 ]; then skipped="$skipped $s"
  elif [ "$rc" -ne 0 ]; then fail=1; fi
done
echo "==========================================="
[ -n "$skipped" ] && echo "SKIPPED (did not run, coverage is missing):$skipped"
[ "$fail" -eq 0 ] && echo "ALL SUITES PASSED" || { echo "SOME SUITES FAILED"; exit 1; }
