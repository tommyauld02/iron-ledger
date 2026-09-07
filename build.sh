#!/bin/sh
# iron-ledger.html is the source of truth: a complete, standalone page you can
# open in any browser. Publishing to a Claude artifact needs it without the
# <head> wrapper (the platform supplies its own), and the tester copy needs a
# different title. Both are generated here — never hand-edit anything in dist/.
set -e
mkdir -p dist

# Windows ships a "python3" stub that only advertises the Microsoft Store, so
# probe by running each candidate rather than trusting `command -v`.
PY=""
for c in python3 python py; do
  command -v "$c" >/dev/null 2>&1 || continue
  "$c" -c "import sys; assert sys.version_info[0]==3" >/dev/null 2>&1 && { PY="$c"; break; }
done
[ -n "$PY" ] || { echo "no working python 3 found (tried python3, python, py)"; exit 1; }

"$PY" - <<'PYEOF'
import io, re
s = io.open("iron-ledger.html", encoding="utf-8").read()
body = re.sub(r'^.*?<body>', '', s, flags=re.S)
body = re.sub(r'</body>\s*</html>\s*$', '', body, flags=re.S)
assert "<title>The Iron Ledger</title>" in body, "wrapper strip went wrong"

# The artifact platform supplies its own head and has no service worker or
# manifest, so the PWA block is dropped from both generated copies.
body = re.sub(r'<!-- pwa:start.*?<!-- pwa:end -->\s*', '', body, flags=re.S)
assert "pwa:start" not in body
# no manifest link means ocrAvailable() is false, so the artifact never
# reaches for vendor/ files that are not published with it
assert 'rel="manifest"' not in body.replace("querySelector('link[rel=\"manifest\"]')", "")
io.open("dist/iron-ledger.artifact.html", "w", encoding="utf-8").write(body)

# the copy handed to testers: different title, build tag marked, no cloud mirror
test = body.replace("<title>The Iron Ledger</title>", "<title>Iron Ledger Test Build</title>")
test = test.replace('"b" + BUILD.split(".").pop()', '"b" + BUILD.split(".").pop() + " test"')
io.open("dist/iron-ledger-test.artifact.html", "w", encoding="utf-8").write(test)
print("dist/iron-ledger.artifact.html      -> publish with capabilities {db, sample}")
print("dist/iron-ledger-test.artifact.html -> publish with capabilities {sample} ONLY")
PYEOF
