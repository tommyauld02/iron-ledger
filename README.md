# MNTL D&T

Diet and training — a gym and macro log, from MNTL. Formerly The Iron Ledger.

One HTML file, no build step, no dependencies, and offline
for everything but one thing: *Ask an agent* asks a free AI about
any food your pantry doesn't know, through a small relay (`relay/`, a
Cloudflare Worker that holds the key) — nothing for the person using it to set
up. Only the food you describe is sent.

## Run it

Open `mntl-dt.html` in a browser. That's it.

To use it on a phone on the same wifi:

    python tools/serve.py

That prints a http://192.168.x.x URL to open on the phone, and serves the app
at "/" the way GitHub Pages does. Service workers need a secure context, so
over plain wifi the app runs but the offline cache does not activate — offline
is only real on the https Pages URL. If the phone cannot reach it, Windows is
probably blocking inbound on a Public network profile.

## Work on it

Read `CLAUDE.md` first — it has the rules that keep this thing from breaking
in the specific ways it has broken before, and an index of `docs/`, where the
architecture is written up one area of the app at a time. Agents working
here also read `TEAM.md`: who does what, the issue labels, and the rule that
nothing merges without the owner's "push it".

    pip install playwright && playwright install chromium
    ./verify.sh        # every suite, phone-emulated (the count is in CLAUDE.md)

On Windows use Git Bash; the scripts find their own Python (`python3` there is
a Microsoft Store stub, not an interpreter).

Nothing ships without that passing. Bump `BUILD` in `mntl-dt.html` on
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

Writes `dist/mntl-dt.artifact.html` (publish with capabilities
`{db, sample}`) and `dist/mntl-dt-test.artifact.html` (publish with
`{sample}` only — never `db`, it makes the artifact unshareable and shares one
store across all viewers). Never hand-edit anything in `dist/`.
