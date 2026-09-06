#!/bin/sh
# iron-ledger.html is the source of truth: a complete, standalone page you can
# open in any browser. Publishing to a Claude artifact needs it without the
# <head> wrapper (the platform supplies its own), and the tester copy needs a
# different title. Both are generated here — never hand-edit anything in dist/.
set -e
mkdir -p dist

python3 - <<'PY'
import io, re
s = io.open("iron-ledger.html", encoding="utf-8").read()
body = re.sub(r'^.*?<body>', '', s, flags=re.S)
body = re.sub(r'</body>\s*</html>\s*$', '', body, flags=re.S)
assert "<title>The Iron Ledger</title>" in body, "wrapper strip went wrong"
io.open("dist/iron-ledger.artifact.html", "w", encoding="utf-8").write(body)

# the copy handed to testers: different title, build tag marked, no cloud mirror
test = body.replace("<title>The Iron Ledger</title>", "<title>Iron Ledger Test Build</title>")
test = test.replace('"b" + BUILD.split(".").pop()', '"b" + BUILD.split(".").pop() + " test"')
io.open("dist/iron-ledger-test.artifact.html", "w", encoding="utf-8").write(test)
print("dist/iron-ledger.artifact.html      -> publish with capabilities {db, sample}")
print("dist/iron-ledger-test.artifact.html -> publish with capabilities {sample} ONLY")
PY
