# The Iron Ledger

Gym and macro log. One HTML file, no build step, no dependencies, works offline.

## Run it

Open `iron-ledger.html` in a browser. That's it.

To use it on a phone, publish it (see below) or serve the folder:

    python3 -m http.server 8000

## Work on it

Read `CLAUDE.md` first — it has the architecture and the rules that keep this
thing from breaking in the specific ways it has broken before.

    pip install playwright && playwright install chromium
    ./verify.sh        # ~190 checks across 16 suites, phone-emulated

Nothing ships without that passing. Bump `BUILD` in `iron-ledger.html` on
every publish.

## Publish

    ./build.sh

Writes `dist/iron-ledger.artifact.html` (publish with capabilities
`{db, sample}`) and `dist/iron-ledger-test.artifact.html` (publish with
`{sample}` only — never `db`, it makes the artifact unshareable and shares one
store across all viewers). Never hand-edit anything in `dist/`.
