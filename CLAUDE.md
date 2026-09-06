# The Iron Ledger

A gym and macro log that runs as a web app on a phone home screen. One HTML
file, no build step, no server, no dependencies. Currently build `2026-09-05.19`.

## The rules, in order of how much damage breaking them does

**1. Nothing ships without `./verify.sh` passing.** 16 suites, ~190 checks. Run
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
eyeballed — `tests/audit2.py` and `tests/mobile.py` enforce it. Destructive
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
build.sh            generates dist/ for publishing (never hand-edit dist/)
verify.sh           runs every suite
tests/              16 Playwright suites
```

## Architecture

**Storage is localStorage first.** That is the only store that works from a
phone home screen, where the page is served top-level and every Claude
capability resolves `null`. `db` is an opportunistic mirror when the app is
opened inside Claude, never a dependency. Backup/restore is copyable JSON,
and the Backup panel shows the build number and the last captured JS error —
that pair has turned an unreproducible bug into a five-minute fix twice.

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

**Days are judged against the goal in force when they were logged.**
`stampGoal()` snapshots it, so changing your target today never rewrites last
month's calendar.

**Dates re-check on wake.** iOS suspends a home-screen app rather than closing
it, so `TODAY` computed once at load meant food logged after midnight landed on
yesterday. `checkDayRollover()` runs on visibilitychange, focus and pageshow.

## Publishing

`./build.sh` writes two files. They differ only in title and build tag.

- `dist/iron-ledger.artifact.html` — the personal copy. Publish with
  capabilities `{db, sample}`.
- `dist/iron-ledger-test.artifact.html` — the copy shared with testers. Publish
  with `{sample}` **only**. Declaring `db` makes an artifact
  organisation-internal and unshareable, *and* its store is shared across
  viewers, so testers would overwrite each other's data.

Bump `BUILD` on every publish. It shows in the header (`b19`) and is stamped
into saved data, which is how you tell a real bug from an iOS cache serving an
old copy. The cache fix is: delete the home-screen icon, refresh in Safari,
re-add.

## Testing

```
pip install playwright && playwright install chromium
./verify.sh          # everything
./verify.sh 8        # last 8 lines per suite
python3 tests/meals.py
```

Suites: `sweep` features · `days` date rollover and month/year boundaries ·
`probe` clicks every tappable and asserts something changed · `darkcheck` WCAG
contrast in both themes · `audit2` touch targets and undo · `coach` routine
builder and history preservation · `meals` combine/split/take out ·
`estmeal` the estimate-as-one-meal path · `touch` real touch events via CDP
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

## Known and deliberate

- The goal bar's centre divider does not line up with the T chart's stem. The
  owner asked to leave that section alone; it is his call.
- Rest days are not painted red on the calendar. Offered, declined.
- Barcode scanning is the one genuine reason to go native. Nothing else found
  so far would have been prevented by a native build.
- The food table is hand-built reference values. Rebuilding it from the USDA
  FoodData Central bulk CSV is the open thread; live API calls are impossible
  from a published artifact anyway (CSP blocks all outbound fetch).
