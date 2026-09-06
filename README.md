# The Iron Ledger

Gym and macro log. One HTML file, no build step, no dependencies, genuinely
offline — it makes no network requests at all.

## Run it

Open `iron-ledger.html` in a browser. That's it.

To use it on a phone on the same wifi:

    python tools/serve.py

That prints a http://192.168.x.x URL to open on the phone, and serves the app
at "/" the way GitHub Pages does. Service workers need a secure context, so
over plain wifi the app runs but the offline cache does not activate — offline
is only real on the https Pages URL. If the phone cannot reach it, Windows is
probably blocking inbound on a Public network profile.

## Work on it

Read `CLAUDE.md` first — it has the architecture and the rules that keep this
thing from breaking in the specific ways it has broken before.

    pip install playwright && playwright install chromium
    ./verify.sh        # ~200 checks across 17 suites, phone-emulated

On Windows use Git Bash; the scripts find their own Python (`python3` there is
a Microsoft Store stub, not an interpreter).

Nothing ships without that passing. Bump `BUILD` in `iron-ledger.html` on
every publish — it versions the service worker cache as well as the header tag.

`audit2` currently reports SKIPPED: it needs `tests/audit.py`, which was not in
the archive this repo was seeded from. That is missing coverage on the 44px
touch-target rule, not a passing test.

## Put it on a phone

Push to `main`. `.github/workflows/pages.yml` runs the suites and, if they pass,
deploys to GitHub Pages. Open the Pages URL on the phone and use Add to Home
Screen — it installs as a standalone app with its own icon and works with no
signal. Nothing leaves the device; the log lives in localStorage.

## Publish as a Claude artifact

    ./build.sh

Writes `dist/iron-ledger.artifact.html` (publish with capabilities
`{db, sample}`) and `dist/iron-ledger-test.artifact.html` (publish with
`{sample}` only — never `db`, it makes the artifact unshareable and shares one
store across all viewers). Never hand-edit anything in `dist/`.
