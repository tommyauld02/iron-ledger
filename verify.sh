#!/bin/sh
# Run every suite against iron-ledger.html. Nothing ships without this passing.
#   ./verify.sh          full output
#   ./verify.sh 6        last 6 lines of each suite
set -e
command -v python3 >/dev/null || { echo "python3 required"; exit 1; }
python3 -c "import playwright" 2>/dev/null || {
  echo "Playwright missing. Run:  pip install playwright && playwright install chromium"; exit 1; }

echo "### testing $(grep -o 'BUILD = \"[^\"]*\"' iron-ledger.html | head -1)"
for s in sweep days probe darkcheck audit2 coach meals estmeal touch mobile \
         commit noclaude yourwords firstrun photo2 taborder; do
  echo "=================== $s ==================="
  if [ -n "$1" ]; then python3 tests/$s.py 2>&1 | tail -"$1"
  else python3 tests/$s.py 2>&1; fi
done
