# Look and touch

Moved word for word from `CLAUDE.md` (issue #10), which keeps the seven
rules and the index of these docs. The rules apply here too.

**The redesign (b66): one theme across the five tabs.** Asked for by the owner
because testers found the app overwhelming; the approved canvas boards are the
design. What holds it together:

- **A header that says where you are.** The wordmark, Backup and Settings as
  icons, then the day in words (*Saturday, Oct 17*), a chip that changes with
  the tab (*5-day streak*, *4 sessions this week*, *2 cardio days this week*),
  and a week strip of seven day buttons. ‹ › still step one day. The strip is a
  calendar row, so like the Log's cells it is exempt from the 44px width at
  320px (it keeps the height).
- **A bar above the tabs that changes with the tab** (`#ctxbar` / `#ctxMain`,
  inside the `.dock`). Macros: *Log numbers*, *Ask an agent* and *Scan*, a
  name under each picture (`docs/food.md`).
  Pantry: find, scan, *New*. Cardio: *Start cardio session*, then the running
  clock with *Discard* and *Stop & log it*. Gym: the rest timer, as before.
  `render()` clears it, so a tab that does not fill it shows none.
- **Pictures for goals.** Macros is a barbell: the bar is calories (it bends,
  then shakes, past the target), the plates are protein, kettlebells are carbs
  and fat when that setting is on. Cardio is a running track where one lap is
  the goal. Over is never bad on either for protein or cardio.
- **Rows open on tap on Macros and Pantry** (Remove is inside the open row,
  with undo). **The Gym keeps every action on screen** — the owner's rule,
  word for word: nothing there moves behind a tap-to-open.
- **The Log peeks before it opens.** A day tapped on the calendar shows what
  it holds in a sheet, with *Open this day*. Coming back to the Log from the
  day it opened finds the Log on the month it was left on (`logOpened`); only a
  day moved to elsewhere makes the Log open on that day's month. Following the
  opened day swapped October, full of history, for an empty August, and the
  owner read it as the past disappearing (video, b67).

**The bottom bars are docked, not stacked.** `.savebar`, `.undobar` and
`.tabs` were each `position: sticky; bottom: 0`, so they sat on top of one
another — `elementFromPoint` at the tab bar's centre returned the undo bar,
meaning undo had always been covering navigation. They now live inside one
sticky `.dock` and stack. `handoff` asserts the tab bar is reachable with each
bar showing.

**With the keyboard up, nothing may make the page shorter.** A phone keyboard
covers the page rather than shrinking it, so while it is up (`html.kb-open`,
read from the visual viewport) the dock steps aside. It used to step aside with
`display: none`: the page lost the dock's height at once, the phone snapped the
scroll to the new end, and the field being typed in slid under the keyboard,
again after every *Add to ledger* (the owner's video, b72). Now the dock is
`visibility: hidden` and keeps its room, the header stops sticking so the date
and week strip don't fill what the keyboard leaves, the page grows by the
keyboard's height (`--kb-h`) so a field at the very end can still be lifted
above it, and `keep()` scrolls the focused field into that band when the
keyboard comes up, changes height or focus moves. Never on a scroll, or
looking up the page mid-entry would be pulled back. Fields in a sheet are left
alone; the sheet already fits. `sweep` stands in a fake visual viewport for
this, since Chromium has no keyboard.

**A long press on a button pops the iOS copy menu.** `.t-row` already guarded
the selection magnifier; `button, [role="tab"]` now guard the same bubble
appearing over a control held a beat too long with a wet thumb. Inputs are
deliberately left out — the backup box has to stay selectable by hand.
`handoff` checks this **against the source and says so in the check name**:
`-webkit-touch-callout` is a WebKit property that Chromium drops on parse, so
there is no computed value and it is not even in `cssText`. A rendered
assertion would pass by measuring nothing, which is the failure this project
has already paid for twice.

**Sheets never squeeze their buttons.** `.sheet-inner` is a flex column, which
shrinks children to fit by default; once What's new listed three updates, its
*Got it* came out 20px tall. Children are `flex-shrink: 0` and the sheet
scrolls.

**Settings: the look is chosen, not just inherited.** The gear sits in the
header beside Backup, so it is on every tab. For now it holds Appearance
(*Match phone* / *Light* / *Dark*) and an accent colour; it is built as
`.set-group` blocks so later settings slot in rather than force a redesign.
`store.theme` and `store.accent` are the truth and travel with a backup; a
restored phone looks like the one it came from.

The CSS already had `:root[data-theme="dark"]` wired in with nothing ever
setting it. `applyLook()` is now the one place that sets it — along with
`data-accent`, the `color-scheme` native controls follow, and the status-bar
`theme-color`, which used to follow only the phone and would have left a white
bar over a dark app for anyone who chose Dark on a light phone.

**The look is applied before the first paint.** A tiny script at the top of the
body reads `iron-ledger-look` — a small key of its own, not the whole log,
which can run to hundreds of kilobytes — and sets the attributes before the
header exists. Without it, someone who chose dark sees a white flash every
time the app opens. `applyLook()` rewrites that key from the store, so the two
reconcile on every load.

**Only the accent moves; hit and miss never do.** Green and red on the
calendar are a meaning, not a decoration, which is also why there is no red or
green among the accents. Each accent is a CSS block keyed on `data-accent` with
a light and a dark variant; teal is the base palette and needs no block. Every
accent was checked before it went in — accent as text on all three surfaces,
button text on the accent, and ink and accent on the soft tint, all 4.5:1 or
better in both themes — and a ticked row has to stay visibly different from
an unticked one. The `.sw-*` swatch colours repeat the palette on purpose, so
the picker shows each accent as it would look in the current theme; `sweep`
applies every accent in both themes and fails if a swatch and what it applies
ever disagree.

**Teal means you can tap it; grey is only a label.** Asked for by the owner,
who could not tell which small words were buttons: an audit found twenty kinds
of text-only control (Edit splits, + Note, Remove, Meals ▾, Take out, ✕…) in
the same grey as the labels beside them. They are teal now, set once in a block
headed *teal means you can tap it* placed after every component's own rule,
rather than patched into twenty places. A button that is a name (a movement, a
meal, a Coach day) keeps its ink and carries a teal marker instead: its ▾, or
*tap to open*. For the rule to mean anything it runs both ways, so teal words
that could not be pressed went grey: the header's day name, the meal tags under
a pantry food, *Superset · 2*, the current month on the Log tab, and the Coach
library's headings. `sweep` walks every tab and fails on either kind of
exception, so the next grey button or teal label is caught, not discovered.

Every press now shows (`button:active` fades to 60%), because most buttons
gave no sign that a tap had landed, and that is how taps get repeated. iOS
Safari applies `:active` only once some `touchstart` listener exists, so the
script adds an empty one. Chromium needs none, so that part is checked against
the source, and the check says so.

The checklist rows on the Pantry tab read backwards for as long as they had
existed: the buttons carried a row span, grid places items with a definite row
first, and the name, left to auto-placement, landed in the last column. Name
and dose are now placed outright.

**`darkcheck` measures only what its fixture puts on screen.** It carried no
meal, no checklist, no running clock and no open review, so every state that
sits on the soft accent tint went unmeasured — and "5 g" on a ticked checklist
row shipped in b36 at 4.08:1. The fixture now has all of them, the walk opens
the estimate review and the Settings sheet, and a second pass chooses every
accent in both themes with the phone set the *opposite* way, so the choice has
to win. It was proven by putting the old colour back and watching it fail.
It also fails if the fixture stops painting any of the three looks of the set
to beat — to beat, beaten, and beaten on a folded card — and `mobile` does the
same for their fit, so a fixture edit cannot quietly turn either into a check
of nothing. The pantry's sections carry the same guard: tabs, a chosen tab,
the meals named under a food and Meals itself must all be on screen, and the
walk opens a food's meals with some chosen, and the meal save row with one.

**A `1fr` column will not shrink below its longest unbreakable line.** The
pantry row's middle column was `1fr` and its macros line `nowrap`, so
`420 kcal · 38 g /container` pushed the page wider than a 320px phone — which
then zooms the whole app out, and every tap `mobile` made landed somewhere
else. Any long unit could always do it; it took the sections fixture's
container to show it. The column is `minmax(0, 1fr)` and the line may wrap.

**The save warning was 2.95:1 in dark mode.** `.savebar` was white on
`--miss`, which is a deep red in light and a light coral in dark. It shows only
when writes are failing, so nothing measured it until `darkcheck` widened from
the tab and undo bars to the whole `.dock`. It now uses `--on-miss`, dark in
the dark theme — 6.38:1. Worth knowing: `darkcheck` reads computed colours, so
it measures a *hidden* element as it would look revealed. That is how it caught
this, and the picker options before it.
