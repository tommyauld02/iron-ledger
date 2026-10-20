# The Iron Ledger

A gym and macro log that runs as a web app on a phone home screen. One HTML
file, no build step, no dependencies. The one server is the food finder's
relay (`relay/`), which holds the AI key so the app needs none.

Started in cowork; it arrived in this repo at build `2026-09-05.19`. The
current build is whatever `BUILD` says in `iron-ledger.html` — do not restate
it here, because a stale number in the first file anyone reads is exactly what
sends someone chasing a phantom.

## The rules, in order of how much damage breaking them does

**1. Nothing ships without `./verify.sh` passing.** 23 suites, ~1,180 checks, 16
of which can fail the build (see Testing — the rest are diagnostics). Run
it after every change, including cosmetic ones — a colour token change once
broke WCAG contrast on every muted label in the app, in both themes.

**2. Test it as a phone, not a laptop.** Every suite runs with
`has_touch=True, is_mobile=True`. Nobody takes a laptop to the gym.

**3. A silent success reads exactly like a dead button.** The worst bug this
app has had was an Add button that saved correctly every single time and said
nothing, while the new row rendered off-screen. The user pressed it repeatedly
and made duplicates. Every action that changes data must visibly say so.

**4. iOS zooms the page on any field under 16px and never zooms back.** There
is a rule forcing every input, select and textarea to at least 16px (a field
may ask for more through `--field-size`, never less). Any new input must not
escape it. `tests/mobile.py` checks this.

**5. 44px minimum on anything tappable, 48px in the tab bar.** Measured, not
eyeballed — `tests/mobile.py` and `tests/handoff.py` enforce it, and
`tests/hittest.py` checks the tap actually reaches the control rather than
something on top of it. Calendar day cells are
the one exemption — a 12-month grid cannot give each day 44px — and both
`mobile` and `handoff` skip them deliberately rather than by accident. Destructive
controls have been the repeat offenders: a delete X at 30×30 near the screen
edge, set chips at 69×29, a Remove button at 52×15.

**6. Deletes offer undo, not a confirmation dialog.** Nobody wants to dismiss a
modal mid-set. Everything destructive calls `offerUndo()`.

**7. History is never silently reassigned.** Rename a training day and old
workouts follow it. Delete one and they say *"Logged under <name> — a day you
no longer train"* rather than being relabelled as a day the user still trains.
`store.retired` holds the names.

## Layout

```
iron-ledger.html    the whole app — source of truth, open it in any browser
vendor/tesseract/   the on-device label reader (see Reading a label below)
vendor/usda/        grocery brands for barcodes (tools/make-brands.py),
                    generated — never hand-edit
relay/              the food finder's relay, a Cloudflare Worker (README.md)
vendor/zxing/       the barcode reader (zxing-wasm 3.1.4), downloaded, not written
fonts/              self-hosted Archivo + IBM Plex Mono (see Fonts below)
icons/              generated — run tools/make-icons.py, never hand-draw
manifest.webmanifest, sw.js   the PWA shell
tools/make-icons.py renders the icons from the app's own colour tokens
build.sh            generates dist/ for publishing (never hand-edit dist/)
verify.sh           runs every suite
tests/              22 Playwright suites, and relay.py, which runs the relay in Node
.github/workflows/  verifies, then deploys to GitHub Pages on push to main
```

**Nothing in `fonts/`, `icons/` or `dist/` is hand-written.** Neither is the
deployed `index.html` — the Pages workflow copies `iron-ledger.html` to that
name at deploy time and does not commit it, because a second copy of the app in
the repo is precisely how this project once spent a while testing green against
a stale build.

## Where the detail lives

How each part of the app works is written up in `docs/`, moved there from this
file word for word so it loads only when it is needed. **Read the doc for an
area before you change it.** The words in *italics* below are the bold titles
of paragraphs in that doc, so searching for one lands on it. New detail goes
into the matching doc, not here: everything in this file is loaded into every
Claude chat.

The areas `TEAM.md` keeps for Nick, because a slip there loses someone's log:

- **Storage and saving** — localStorage first, the `db` mirror, `save()` and
  `saveError`, no expiry and no cap → `docs/architecture.md` (*Storage is
  localStorage first*, *A failed write must never look like a successful one*)
- **Backup and restore** — `lastBackupAt`, the backup dot, *Send a copy* →
  `docs/architecture.md` (*On a phone there is no second copy*)
- **Undo** — `offerUndo()`, `undoStack`, runs, `noteSave()`, `screenKey()` →
  `docs/architecture.md` (*Undo walks back, one press at a time*)
- **Dates** — `TODAY`, `checkDayRollover()`, the goal stamped on each day →
  `docs/architecture.md` (*Dates re-check on wake*, *Days are judged against
  the goal in force*); clocks left running past midnight → `docs/gym.md` (*A
  forgotten clock records nothing*) and `docs/cardio.md`
- **Service worker and PWA** — `sw.js`, network-first documents, cache
  versions, registration → `docs/architecture.md` (*The app is installed*);
  the data cache for brands and the barcode reader → `docs/food.md` (*The
  service worker keeps it across builds*)

Everything else:

- **What's new and `NEWS`** — an entry with every build a person would notice
  → `docs/architecture.md`
- **Rendering** — the full redraw into `#view`, delegated handlers →
  `docs/architecture.md`
- **Fonts** → `docs/architecture.md` (*Fonts are self-hosted*)
- **Look and touch** — the dock, long press, sheets, Settings, theme and
  accent, teal means you can tap it, contrast, `darkcheck`'s fixture →
  `docs/ui.md`
- **Logging food** — the three ways in, the words box, folded boxes and
  pop-ups, grams and units, meals → `docs/food.md`
- **The food finder** — the free AI that answers what the pantry doesn't know,
  the relay that holds its key, the self-check → `docs/food.md`; deploying the
  relay → `relay/README.md`
- **Reading a label**, grocery brands, barcodes → `docs/food.md`
- **Carbs and fat, water, body weight, the goal calculator** → `docs/food.md`
- **Pantry** — part-name matching, the `+` sheet, counts, saved and combined
  meals, sections → `docs/pantry.md`
- **Daily checklist** (supplements) → `docs/pantry.md`
- **Gym tab** — the workout clock, Done and laps, sets and the set sheet,
  techniques, supersets, the drag, the rest timer, movement lists, the
  week's plan →
  `docs/gym.md`
- **Targets** — compare with last time, special day, notes, the set to beat,
  five pounds a rep, gyms, last time set by set → `docs/gym.md`
- **Cardio tab and cardio goals** → `docs/cardio.md`
- **Testing in detail** — what each suite covers and the lessons behind them →
  `docs/testing.md`
- **Sharing a routine** — the Coach tab, `ILROUTINE1:` codes, the day-id trap,
  never through `mergeInto` → `docs/sharing-a-routine.md`
- **Known and deliberate** — what is left as it is on purpose, including
  *Ask an agent* needing a connection → `docs/known-and-deliberate.md`

## Publishing

`./build.sh` writes two files. They differ only in title and build tag.

- `dist/iron-ledger.artifact.html` — the personal copy. Publish with
  capabilities `{db, sample}`.
- `dist/iron-ledger-test.artifact.html` — the copy shared with testers. Publish
  with `{sample}` **only**. Declaring `db` makes an artifact
  organisation-internal and unshareable, *and* its store is shared across
  viewers, so testers would overwrite each other's data.

Bump `BUILD` on every publish. It shows in the header (`b19`) and is stamped
into saved data, which is how you tell a real bug from a stale copy. It is also
what versions the service worker cache.

The old cache fix — delete the home-screen icon, refresh in Safari, re-add —
should no longer be necessary on the Pages build, because documents are fetched
network-first. If you ever find yourself needing it again, that is a service
worker bug, not an iOS quirk to work around.

## Testing

```
pip install playwright && playwright install chromium
./verify.sh          # everything
./verify.sh 8        # last 8 lines per suite
python3 tests/meals.py
```

`verify.sh` and `build.sh` find their own interpreter. Windows ships a `python3`
that satisfies `command -v` but only advertises the Microsoft Store, so they
probe candidates by running them, and `verify.sh` forces UTF-8 on the children —
a cp1252 console dies on the `✕` the suites print. The suites normalise
`os.getcwd()` into a `file:///C:/...` URL; that is a no-op on POSIX.

**Which suites can actually fail the build.** For a long time the answer was
"two". Every other suite printed `N passed, M FAILED` and exited 0, so
`verify.sh` said ALL SUITES PASSED with failures on screen — proven by
injecting a deliberate failure into `sweep` and watching CI stay green. That
is fixed, and it is worth keeping straight:

- **Gates** (exit non-zero on a failed check *or* a page error): `sweep`,
  `days`, `week`, `coach`, `meals`, `estmeal`, `touch`, `mobile`, `darkcheck`, `pwa`,
  `handoff`, `finder`, `relay`, `label`, `hittest`, `share`.
- **Diagnostics** (print only, always exit 0): `probe`, `commit`, `noclaude`,
  `yourwords`, `firstrun`, `photo2`, `taborder`. These are read by a human.
  Converting them needs judgement about what counts as a failure — `probe`'s
  standing "1 need a look" is the label photo button, which opens a native
  picker and so changes no DOM. It is alive; verified with the `filechooser`
  event.

Everything else about the suites — what each one covers, `hittest`, the
controls that only exist after a press, exit code 77, CI on Linux and the
lessons paid for the hard way — is in `docs/testing.md`.
