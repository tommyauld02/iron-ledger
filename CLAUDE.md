# The Iron Ledger

A gym and macro log that runs as a web app on a phone home screen. One HTML
file, no build step, no server, no dependencies.

Started in cowork; it arrived in this repo at build `2026-09-05.19`. The
current build is whatever `BUILD` says in `iron-ledger.html` — do not restate
it here, because a stale number in the first file anyone reads is exactly what
sends someone chasing a phantom.

## The rules, in order of how much damage breaking them does

**1. Nothing ships without `./verify.sh` passing.** 21 suites, ~395 checks, 14
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
is a `@media (pointer: coarse)` rule forcing 16px. Any new input must not
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
fonts/              self-hosted Archivo + IBM Plex Mono (see Fonts below)
icons/              generated — run tools/make-icons.py, never hand-draw
manifest.webmanifest, sw.js   the PWA shell
tools/make-icons.py renders the icons from the app's own colour tokens
build.sh            generates dist/ for publishing (never hand-edit dist/)
verify.sh           runs every suite
tests/              21 Playwright suites
.github/workflows/  verifies, then deploys to GitHub Pages on push to main
```

**Nothing in `fonts/`, `icons/` or `dist/` is hand-written.** Neither is the
deployed `index.html` — the Pages workflow copies `iron-ledger.html` to that
name at deploy time and does not commit it, because a second copy of the app in
the repo is precisely how this project once spent a while testing green against
a stale build.

## Architecture

**Storage is localStorage first.** That is the only store that works from a
phone home screen, where the page is served top-level and every Claude
capability resolves `null`. `db` is an opportunistic mirror when the app is
opened inside Claude, never a dependency. Backup/restore is copyable JSON,
and the Backup panel shows the build number and the last captured JS error —
that pair has turned an unreproducible bug into a five-minute fix twice.

**A failed write must never look like a successful one.** `save()` returns a
boolean and sets `saveError`; it used to be `catch (e) { /* quota */ }`, which
meant the app rendered the row, printed "✓ Added" and lost the entry on the
next load. Every caller that claims success — the add-food flash, the Add
button, the pantry `+` tick — is gated on that boolean, and while writes are
failing the `#savebar` says so until one succeeds. The reason is also written
into `lastError`, so the Backup panel names it. Storage being full is only one
trigger: the same path fires in private browsing and under iOS storage
pressure, which arrive long before the quota does.

**The bottom bars are docked, not stacked.** `.savebar`, `.undobar` and
`.tabs` were each `position: sticky; bottom: 0`, so they sat on top of one
another — `elementFromPoint` at the tab bar's centre returned the undo bar,
meaning undo had always been covering navigation. They now live inside one
sticky `.dock` and stack. `handoff` asserts the tab bar is reachable with each
bar showing.

**Nothing expires, and there is no cap.** No pruning, no cutoff, no bound on
the date or year arrows — `store.days` keeps every day forever. A fully logged
day costs about 1.1 KB, so a 5 MB origin holds roughly 4,700 days, about
thirteen years. Capacity is not the constraint; the write path is.

**On a phone there is no second copy.** `db` only exists inside the Claude
viewer, so on the Pages build `queueSync()` returns immediately and
localStorage is the only place the log lives. Nothing else notices if it goes.
The app therefore records `store.lastBackupAt` whenever a copy actually
reaches the clipboard, and after 14 days — or if no copy has ever been taken —
the header Backup button carries a dot and the panel says how long it has
been. The dot uses the accent, not `--miss`: nothing is broken, there is just
something worth doing. `lastBackupAt` is deliberately **not** merged on
restore, because a phone you have just restored onto has not taken a copy of
its own and should still be asked for one.

**Your pantry answers to part of its name.** A pantry entry used to be found
only by its whole name, so someone who saved "Costco protein coffee" and later
typed "protein coffee" missed the pantry entirely and got the table's black
coffee — 1 kcal logged for a 130 kcal drink, with nothing to suggest anything
was wrong. `matchPantryItem()` now also matches when what you typed appears as
a run of words inside the saved name, two words minimum so a bare "coffee"
still means coffee, and it tries a singular form so "2 protein coffees" lands.
`parseQty()` drops a leading article too: "half a protein coffee" used to leave
"a protein coffee" behind, which matched nothing.

**Reading a nutrition label.** Inside the Claude viewer the `sample` capability
reads the panel and can name the product. On the hosted copy there is no
capability, so the panel is read on the device with Tesseract from
`vendor/tesseract/` — 14.4 MB, and **the app's one dependency**. It is loaded
lazily: nothing is fetched until the button is pressed, so the offline core
stays at 150 KB, and the service worker keeps it afterwards so later scans work
offline. It is deliberately absent from the worker's precache list.

The calorie figure is found by **how it is printed**, not by reading order. It
is set far larger than anything else on a panel, and OCR splits it into
separate digit-words and scatters them through the text — a plain text scan
pulled *609* out of a blurred panel, which is exactly the confident wrong
number rule 3 exists to stop. `readPanel()` takes the tallest numeric words
sitting on one line and reads them left to right.

Nothing it cannot read is guessed. A panel carries plenty of numbers larger
than the calories — sodium in mg, carbs, every % daily value — so a "take the
biggest number" fallback would log sodium. Blank fields go into the form and
the person fills them, which is safe because the reader fills the *form*, never
the ledger. **The product name is not on the panel** — that is front-of-pack
branding — so it is always left empty.

The vendor files are downloaded, not written: the wrapper and worker from
tesseract.js 5.1.1, the SIMD LSTM core, and the standard English model. The
small `tessdata_fast` model is a third of the size and was rejected — it missed
protein on a blurred panel, and protein is half of what this app tracks. Only
the SIMD core is shipped, which needs iOS 16.4 or newer.

**Offline answers first, Claude second.** The built-in ~115-food table and the
user's pantry resolve most entries with no network and no account. `sample` is
the fallback for what they can't handle. This has broken twice in the same way:
a code path that checked "is Claude available?" *before* trying the offline
table, so the offline capability was silently dead on the phone. If you write
`if (sampleFn)`, ask whether the offline path should run first.

**Rendering is a full redraw into `#view`, wrapped in try/catch.** Handlers are
delegated on `#view` and the tab bar, which are never replaced — an earlier
version wired handlers sequentially after a long render, so one throw left
every later button dead and silent. If `render()` throws on the Macros tab, a
plain fallback view still lets you log.

**Meals read through, never store.** A meal is `{id, note, items:[...]}`. Its
calories and protein come from `rowCal()`/`rowPro()` summing the items on every
draw — never written onto the meal — so the day total cannot drift from its
contents no matter how much you combine, split, take out, and undo. Meals never
nest; combining flattens. `tidyMeals(d)` is the single rule that a meal of one
or zero items dissolves back into plain rows — call it after anything that can
remove an item. `locate(d, id)` finds a row at the top level *or* inside a meal;
use it anywhere food is looked up by id.

**The way in is a table, not a blank box.** "What did you eat?" over an empty
textarea tells someone opening the app for the first time nothing about what it
accepts — the owner said so, and he was right. Macros now opens on labelled
fields with examples in them, the shape the pantry form already uses: Amount /
Unit / Food, one row per item, `+ Add another`, and a datalist on the food field
carrying every name in `FOODS` plus the pantry, so "what does it know?" is
answered by typing rather than by guessing and being told no.

The plain-words box did **not** go away. It is what makes "half a protein
coffee" and "chicken and rice" work in one line, and it is faster once you know
the shape, so it sits behind *Or just describe it in words* and takes over the
form when opened. Swapping to it carries the table across as text — but never
over the top of words already in the box.

The table is a way to **compose** the same sentence, not a second code path:
`rowChunk()` turns one row into `"6 oz chicken breast"` and `rowsText()` joins
them with `&`, which is exactly what `splitItems()` already splits on. Pantry,
the built-in table and Claude resolve it unchanged. Every unit the picker offers
is a word `parseQty()` knows, so the picker cannot produce a chunk the parser
then shrugs at.

Two things that are easy to get wrong here. `estRows` empties on commit along
with `estDraft` — leaving the rows filled in is how someone logs the same meal
twice without noticing. And pressing *Work out the macros* with nothing filled
in sets `estHint` and says so; doing nothing at all would read exactly like a
dead button.

The suites feed the resolver through the words box, so the ones testing food
matching rather than entry call a local `words(p)` helper first. `sweep` and
`estmeal` drive the table itself, because that is the front door now.

**Grams are the basis; the unit is only how it is shown.** The whole food
table is keyed per 100 g and every macro is derived from `it.grams`, so that
is what gets stored and nothing downstream has to know what unit you like.
`WEIGH` maps g/oz/lb to grams, `fromG()`/`toG()` convert at the edges, and
`store.wunit` is the standing choice — set it under *Weigh food in* on the
estimate form, or from the picker on any review row.

Two rules make it safe. **Switching a unit converts, it never re-reads**: 150 g
becoming 150 oz is a four kilogram chicken breast logged in one tap, so the
food stays the same size and only the reading changes; you then type over it if
you meant something else. And **a weight you typed comes back in the unit you
typed it in** — someone who entered "6 oz" and is shown 170 g has to do
arithmetic to check their own entry, so `resolveTable()` and `resolvePantry()`
carry the typed unit through as `it.unit`. A row with no unit of its own
follows `store.wunit`, which is why changing one row redraws the review rather
than patching one field.

The standing picker and a review are never on screen together — the review
replaces the form — so there is deliberately no "update the open review" branch
on it. Mid-review, the row picker is the way.

**Days are judged against the goal in force when they were logged.**
`stampGoal()` snapshots it, so changing your target today never rewrites last
month's calendar.

**The app is installed, not just bookmarked.** `manifest.webmanifest` and
`sw.js` make it a real PWA: standalone display, home-screen icon, and an
offline shell. The service worker is **network-first for documents** and
cache-first for fonts and icons. That direction is deliberate and is the fix
for the iOS-serves-an-old-build problem this project kept hitting — online you
always get the current build, offline the cache answers. The worker reads its
version from its own `?v=` query, which the app sets from `BUILD`, so there is
no second version to bump.

Registration is gated on the app's own `<link rel="manifest">`, not on the
protocol. Artifacts are https too, so a protocol test would send them chasing a
`sw.js` that isn't there and write a phantom error into the Backup panel;
`build.sh` strips the manifest link from both artifact copies, so they never
register.

**Fonts are self-hosted.** Google Fonts was the only outbound reference in the
whole file and there are no `fetch` calls anywhere, so removing it made the app
genuinely offline. Archivo is a variable font — one file per subset spans
400–700, and Google serves the same bytes for every weight you ask for, so do
not re-add per-weight Archivo files. IBM Plex Mono is static, one per weight.
Latin and latin-ext only.

**Dates re-check on wake.** iOS suspends a home-screen app rather than closing
it, so `TODAY` computed once at load meant food logged after midnight landed on
yesterday. `checkDayRollover()` runs on visibilitychange, focus and pageshow.

**The workout clock is a timestamp, not a counter.** `d.workoutStart` is when
you pressed Start; the elapsed time is always `now - workoutStart`, computed
fresh. Nothing counts up in a variable, which is the whole point — iOS suspends
the app the moment you put the phone in your pocket, and a counter would come
back reading two minutes for a ninety minute session. `d.workoutMs` is what has
been banked, and the two **add**, so a second session on the same day tops up
the first rather than replacing it.

The clock sits **above** *Today's split*, not below it. It is the first thing
you touch walking in and the last before you leave; it should not be something
you scroll to find.

*Lock in the day* is what stops it: `lockDay` calls `stopWorkout(d)` before
anything else, so the number the card shows is the number that gets stored. The
running clock is redrawn by a `setInterval` that writes into `#workoutClock`
directly rather than calling `render()` — a full redraw once a second would
fight anything being typed into a weight field. One interval, cleared and
restarted on every draw, and it clears itself if the element it writes to is
gone.

Discard exists because a mis-tap at nine in the morning otherwise becomes a six
hour session, and it goes through `offerUndo()` like everything else
destructive. The calendar and the Log tab's *Avg session* read **banked** time
only: a clock still running is not a finished session and must not drag the
average down all afternoon.

**A forgotten clock records nothing rather than a lie.** Nobody locks in the
day from the car park, so a clock is going to be left running overnight — and
`14:32:07` on a calendar day is precisely the confident wrong number rule 3
exists to stop. Two things handle it. `checkDayRollover()` stops the clock on
the day it started on, because a session belongs to the day you trained, not
the day you next opened the app. And `stopWorkout()` banks a run only if it is
under `MAX_SESSION_MS` — six hours, generous for the longest real day anyone
has in a gym. Past that the time is dropped, the way the label reader leaves a
field it could not read empty. The lifts are untouched; the day simply does not
claim a duration.

Dropping it silently would be the same bug from the other end, so the running
bar names the state before you get there: past the bound it goes `.is-stale`,
loses the accent, reads *Left running*, and says the time will not be saved.
The once-a-second tick only writes digits, so it hands over to one `render()`
at the moment the bound is crossed and stops.

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
  `days`, `coach`, `meals`, `estmeal`, `touch`, `mobile`, `darkcheck`, `pwa`,
  `handoff`, `foods`, `label`, `hittest`, `share`.
- **Diagnostics** (print only, always exit 0): `probe`, `commit`, `noclaude`,
  `yourwords`, `firstrun`, `photo2`, `taborder`. These are read by a human.
  Converting them needs judgement about what counts as a failure — `probe`'s
  standing "1 need a look" is the label photo button, which opens a native
  picker and so changes no DOM. It is alive; verified with the `filechooser`
  event.

`hittest` came from the cowork project and asks what the size audit cannot:
when you tap the middle of a control, does the tap reach it, or is something
on top? It scrolls in viewport-sized steps because `elementFromPoint` only
answers inside the viewport, and it ignores a corner clipped by an ordinary
neighbour while flagging one taken by something floating over the layout. It
was print-only as it arrived and now exits non-zero, because a control a tap
cannot reach is a dead button by another name.

**A control that only exists after a press is the blind spot this app keeps
falling into.** Three times now: the finished-day card's contrast, the split
editor's fit, and three naming fields that shipped 23px tall because
`.rt-inline` centres its children and they never stretched. Nothing that walks
the tabs as it finds them will ever paint these. `handoff` now opens every one
of them — meal name, rename a day, add a movement, add a day, add a split —
and measures it for 44px and the 16px iOS-zoom rule.

When you add a suite, end it the way the gates do. A suite that reports FAIL
and exits 0 is a report wearing a test's clothes, and rule 1 quietly stops
meaning anything.

A suite exiting **77** means it could not run at all, which is not the same as
the app being broken. `verify.sh` names those separately at the end and still
exits 0. Nothing uses it at the moment.

**`audit2.py` was deleted rather than repaired.** It read a `MEASURE` snippet
from an `audit.py` that only ever existed in the original author's working
directory, so from the day this repo was seeded it did nothing — and the old
`verify.sh` piped every suite into `tail`, which threw away the exit code, so
the traceback scrolled past looking like an empty section. Its job is done
twice over now: `mobile` and `handoff` measure every control against the 44px
rule and gate on it, and `hittest` checks the tap reaches the control. Two
lessons worth keeping: a helper outside the repo is a suite that only works on
one machine, and a suite whose exit code is discarded is not a test.

Suites: `sweep` features · `days` date rollover and month/year boundaries ·
`probe` clicks every tappable and asserts something changed · `darkcheck` WCAG
contrast in both themes · `coach` routine
builder and history preservation · `meals` combine/split/take out ·
`estmeal` the estimate-as-one-meal path · `pwa` the offline shell, served the
way Pages serves it, with the network cut · `handoff` safe-area opt-in, all
three wake paths, measured touch targets on a 402x874 phone, and the
no-Claude-and-no-network mode Pages actually runs in · `touch` real touch
events via CDP
including the press-and-hold drag · `mobile` fit and font audit across five
iPhone sizes · plus `commit`, `noclaude`, `yourwords`, `firstrun`, `photo2`,
`taborder`.

Two lessons paid for the hard way:

- **A test that measures hidden elements passes while measuring nothing.** A
  touch-target check reported green because no panel was open. Assert the
  elements are on screen before asserting anything about them.
- **Tests ran for a while against a stale generated copy** and passed
  everything against an old build. The suites now read `iron-ledger.html`
  directly, so there is nothing to go stale.

## Sharing a routine

The Coach tab exists so someone else can set a routine for the owner — a
brother, a friend. Nothing ships for that yet, and the groundwork matters more
than the feature.

**Built, and built to the shape below.** Coach has *Share this routine* and
*Load a routine*. Sharing produces `ILROUTINE1:` followed by base64 — base64
rather than raw JSON because the code gets sent through messaging apps, where
JSON meets smart quotes and line wrapping. `parseRoutineCode()` is liberal in
return: tagged or untagged, wrapped over lines, or plain JSON if that is what
someone pasted.

**The export carries no ids at all.** That is the whole design. Rather than
guarding against a collision, `exportRoutine()` sends only names and movements,
and `importRoutine()` mints a fresh `"d" + uid()` for every incoming day — so
two people who both still have `back`, `push` and `legs` cannot collide,
because nothing of theirs is ever adopted. Days are **added**, never swapped
in, and the whole import is one `offerUndo()`.

It carries the routine and nothing else: no food, no lifts, no pantry, no goal,
no dates. `tests/share.py` asserts that by looking for those keys in the
decoded payload.

**Do not route sharing through `mergeInto`.** Restore and import are different
operations wearing similar clothes. `mergeInto` does
`store.routine = incoming.routine` — a wholesale replace, which is right for
your own backup landing on your own phone and wrong for anything else.

**The trap is day ids.** `DEFAULT_ROUTINE` uses fixed ids — `back`, `push`,
`legs` — so two people who never renamed their days have *the same ids for
different days*. Feeding another person's routine through restore today is
demonstrably rule 7 broken: a workout logged under your `back` renders under
their name for `back`, `store.retired` stays empty, and nothing records what
the day was called when you trained it. Verified, not theorised.

So an import path must **remap incoming day ids to fresh ones** before
anything touches the store, and must add days rather than replace them.
`addSplit()` already mints `"d" + uid()`, which is collision-safe; only the
three seeded defaults are not, and they cannot be renamed retroactively
without orphaning the history of everyone already using them.

**Movements collide the same way.** `mergeInto` merges `incoming.moves[id]`
into `store.moves[id]` by id, so their bench press lands in your back day if
the ids happen to match. Remapping ids first fixes this too.

## Known and deliberate

- The goal bar's centre divider does not line up with the T chart's stem. The
  owner asked to leave that section alone; it is his call.
- Rest days are not painted red on the calendar. Offered, declined.
- Barcode scanning is the one genuine reason to go native. Nothing else found
  so far would have been prevented by a native build.
- The food table is hand-built reference values, 310 of them, weighted towards
  what actually moves a calorie count: meats, grains, starches, fats, prepared
  meals. Produce is covered but deliberately not expanded — a stick of celery
  is not what breaks a day. Rebuilding it from the USDA FoodData Central bulk
  CSV is the open thread; live API calls are impossible from a published
  artifact anyway (CSP blocks all outbound fetch).

  Fast food is in there — 45 chain items, because "no time to cook" is when
  someone least knows what they ate. Those are stored the same way as anything
  else, per 100 g, with `k` derived from the published total and the serving
  weight so that one serving reproduces the total even if the gram figure is
  a little off. **Brand values drift** as chains reformulate; treat them as a
  close estimate, not a label reading. A counted item must carry `each` as
  *one piece*, not one box — a ten-piece nugget entry with `each: 162` turned
  "10 mcnuggets" into 4,201 calories.

  `tests/foods.py` guards it, because growing it broke twice in ways nothing
  else caught. Adding an entry after the last one killed the whole script — the
  final entry had no trailing comma. And `splitItems()` splits on the words
  "and" and "with" *before* matching, so "mac and cheese" resolved to cheddar;
  aliases containing those words are now stitched back together across the
  split, using an underscore rather than a control character, because `and`
  still matches across a non-word one. Unit keys are checked too: `medium`,
  `large` and `small` are typed words that map to the key `each`, so a `u:` map
  keyed by them is never read.
