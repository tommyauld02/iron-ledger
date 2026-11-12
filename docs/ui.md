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
alone; the sheet already fits.

**`keep()` moves the page once and never argues with the phone.** On b74 it ran
on every `visualViewport` resize. iOS reports resizes while it settles its own
scroll, and moves the page to where it wants the focused field; `keep()` moved
it back, and the two took turns ten times a second until the keyboard was put
away. Ask an agent, opening in place at the foot of Macros, flickered between
its box and the ledger (the owner's video, b74). Now `keep()` waits for the
keyboard to stop changing height (`keepSoon()`, 320 ms since b76), moves the page at
most once, and ignores resizes that are not the keyboard changing height by
2px or more. `--kb-h` only grows while the keyboard is up, so a keyboard that
wobbles by a pixel never makes the page shorter. `sweep` plays the phone's
half: it moves the page after the lift and keeps reporting the same keyboard,
and the app must not move it back. `sweep` stands in a fake visual viewport for
this, since Chromium has no keyboard.

**The room under the page comes before the keyboard and leaves after it.** On
b75 the room (`--kb-h`) grew as the keyboard came up. iOS showed Ask an
agent's box, the page grew under it mid-animation, and iOS dropped the page
back to the ledger with the box behind the keyboard until a letter was typed.
Putting the keyboard away took the room out at once, and the phone slid the
page up a keyboard's height over a second and a half (the owner's video, b75).
Now `room()` puts it there on `focusin`, before the keyboard has begun to
arrive, sized past any phone keyboard (55% of the window; it still grows if a
keyboard is taller). It is `html.kb-room`, separate from `kb-open`. When typing
ends, `dropRoom()` takes it out only once it is off the screen: space below
what is showing goes without moving anything. `keepSoon()` waits 320 ms, long
enough for iOS to have placed the field itself, so `keep()` is the fallback
rather than a second opinion. `sweep` checks the room is there on focus, that
the keyboard arriving changes no height, and that putting the keyboard away at
the foot of the page leaves the page where it was.

**The room goes above the dock, and keeps only what is showing (b87).** The
room was `.app`'s padding, which put it *below* the dock: put the keyboard away
near the foot of a page and the dock hung over an empty stretch, the b77
video's symptom on the web. It is `main`'s padding now, so the dock stays at
the bottom of the screen. And once typing ends, `dropRoom()` shrinks the room
to what is on screen rather than keeping all of it until it is out of sight:
the page never moves and never gets shorter under the eye, and there is never
more blank to scroll down into than was already showing. A page shorter than
the screen, seen from its top, is the one exception (b90): there the room could
never scroll out of sight, so it kept a two-pixel sliver to scroll after every
note typed on an empty Progress tab. Taking all of it out moves nothing there,
so it goes. `progress` checks it under a stand-in keyboard.

**A field in the dock lifts the dock (b87).** *Find in your pantry* is in the
dock, and the dock hides while typing, so the field vanished mid-word. When the
focused field is in the dock (`kb-dock`), the dock stays and is lifted by
`--kb-lift` to sit on the keyboard, the tabs behind it; it needs no room.

**A field in a sheet is brought up inside the sheet (b87).** The sheet fits what
the keyboard leaves, but its contents can be taller: on a 320px phone the set
pop-up's Reps went under the keyboard. `keep()` scrolls the sheet's own
`.sheet-inner`, never the page, once per keyboard; it does this in the iPhone
app too, since the WebView only moves the page. `keys` checks all three, on
every field the app has.

**In the iPhone app the WebView handles the keyboard, and the page leaves it
alone.** The owner's video (b77, the TestFlight app): iOS lifted Ask an
agent's box above the keyboard, then the page was pulled back to the ledger
with the box behind it. After Log numbers, the dock hung halfway up the
screen over an empty page once the keyboard went. The app's WebView already
makes the page scrollable past its end by the keyboard's height and lifts the
field itself, so the room and `keep()` on top of that were a second correction
to a page that was already right. When `NATIVE`, `room()` adds nothing and
`keep()` never moves the page. `kb-open` still hides the dock and fits a
sheet. The Pages web app keeps everything above. `sweep` stands in for the
bridge (`keyboard (app)`): no room on focus, the keyboard arriving moves
nothing and adds no height, and the page is its own height once it goes. What
it cannot show is the WebView's own lift, since Chromium has no keyboard.
Only the phone can check that.

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

**Chalk and Iron (b96): a new look, in four steps.** Asked for by the owner,
who had only ever seen the look the app was born with and wanted "an upgrade":
"more artistic", something "that refers to the gym". The first concept put a
home screen of doors in front of the tabs; he turned it down, because hiding
features behind a tap makes them harder to find, not more inviting. What he
kept from it: a dark stage with a light sheet, one action button, and Pantry
inside Macros. His two conditions for the look itself: **every feature and
every setting carries over** ("everything before were all added with
intention"), and **there is room for what comes later** (friends, a shared
cookbook, a leaderboard) without another redesign. The pieces come from a gym:
a black rubber floor, placard lettering, stencilled labels, a weight stack, a
plate, one line in chalk.

It is built in four steps so that only one thing is in question at a time:
1. **The look, with nothing moved (b96).** This step.
2. The stage and the sheet: lists slide over the picture, which shrinks to a
   bar and stays.
3. The plate: one action button in place of the three-button bar.
4. Pantry moves inside Food.

**Step 1 is one block of CSS** at the end of the main `<style>`, headed
*CHALK AND IRON, step 1*. No markup and no behaviour changed, which is the
point of the step: a control that is where it was cannot be lost.

- **The floor is a scope, not a theme.** `.topbar`, `.today-card`,
  `.session-card`, `.cardio-goal`, `.year-card`, `.pan-bar`, `.dayline` and
  `.tabs` redeclare the palette with the dark theme's values over `--floor`,
  a ground darker than any the dark theme uses. Those pairings have been
  measured by `darkcheck` for years and only gain contrast on a darker
  ground. Each accent has a rule of its own for the floor, because an accent
  block sets its colours on `:root` and the scope would otherwise keep teal.
  The floor is the same in light and dark: a rubber floor does not change
  with the lights. **Anything new that stands on the floor must be added to
  the scope's selector list**, or it will draw dark ink on black.
- **A colour is asked of the thing, not of the page.** On the floor
  `--accent`, `--gold` and `--plate` are not what `:root` says. `sweep`'s
  teal walk and its gold checks resolve the token on the element they are
  judging, since b96.
- **Three display faces**, used large and never for running text: Big
  Shoulders Display for numerals and headings, Big Shoulders Stencil Display
  for labels, Caveat Brush for the daily line and nothing else
  (`docs/architecture.md`, *Fonts are self-hosted*).
- **Capitals are lettering, not wording.** Headings and buttons are
  upper-cased by CSS, so the words in the source and in `textContent` are as
  they were written. A check that reads a button's words uses `text_content`;
  `inner_text` returns what is drawn.
- **The tabs are a weight stack**: a slab a tab, a hole in each, and a pin in
  the one you are on (`::after` on the selected tab, which drops in; no
  script). The slabs have a gap, which is part of the bar when it is measured.
  Seven tabs still fit a 320px phone.
- **The week is seven small plates**, the number in a ring; the mark under it
  is unchanged.

**Gold means you earned it (b94).** Asked for by the owner after a review
found that wins were quiet: beating the protein goal changed almost nothing on
screen. It is the third colour rule, beside teal for tap and green and red for
hit and missed, and it has one meaning, so nothing you can tap is gold and no
accent is. Three things are gold, and a good week's daily line (below, b95)
makes four. Only these:

- **The plates**, once an "at least" protein goal is reached *with the bar
  still steady*, and nothing waiting for numbers (`barWon()`). Over on calories
  is not a win. That also keeps gold off a bar that is yellow for being a
  little over, since `--warn` is a yellow too and the two must never sit on one
  bar saying different things. Every bar drawn for the day agrees: Macros, the
  Pantry's, and *Your bar after this*.
- **The note under the bar** (`.hit-note`), which was green until b94. It only
  ever shows when the plates are gold, so it is the same condition and the same
  gold, with a star where the tick was. The protein figure and the card's edge
  go gold with it.
- **A streak of three days or more**, on the Macros chip, with a flame.

The bar can be off the top of the screen when the food that wins the day goes
in from *Log numbers* lower down, so the *Added* confirmation under the ledger
says it as well, in gold, where the eye already is (`lastAdded.won`).

The turn to gold plays once, on the draw that crosses the line: the iron lifts
off each plate from the collar outward after the last new plate lands, the note
stamps in, and the iPhone app gives the success buzz. `barPrevWon` remembers
what each bar last drew and for which day, so arriving at a day already won, or
opening the app on one, plays nothing. Reduce Motion keeps the gold and drops
the movement. A kettlebell can still be yellow beside gold plates (carbs a
little over on a day protein is hit); the owner has been shown that and not yet
said whether the warning should move to orange.

`sweep` checks each state that must be gold beside the ones that must not
(short, over on calories, a food waiting, an "at most" goal, a two-day streak).
`darkcheck` measures every pairing gold is used in, holds the plates to 3:1 on
the card as a picture, and has a pass of its own that puts the won day on
screen, because the main fixture is short of protein on purpose. It was proven
by weakening the gold words and watching it fail in light.

**The daily line (b95): one line about your week, and Got it.** Asked for by
the owner in his own words: *"your protein goals have not been hit for the past
5 days, be sure to get in more protein dense foods"*, *"your weekly schedule
wasn't hit last week"*, *"calorie goal was missed 2 days last week"*, and for a
good week, *"7 out of 7 days cardio were hit last week, keep it up!"*. He had
just turned down a box of pantry foods with + buttons under the barbell as
unnecessary clutter, so this is words and one button, never controls: a slim
strip (`.dayline`) at the top of the tab it is about. A reminder carries the
calendar's red as a dot; a good week is gold with a star, because it was
earned. Most days there is none.

His lines were examples. Asked whether to stop at them, he said to *"implement
more that are in line with what the goal is"*, so each tab also speaks to the
other goals it holds. What each can say (`lineCandidates()`), reminders first
and in this order, then the good ones:

- **Macros, reminders.** Nothing logged for three days or more, to someone who
  was logging before and has nothing in today yet (`gap`). Protein missed three
  or more days running, counted back from yesterday (`pro-run`); failing that,
  protein missed two or more days last week (`pro-week`). Calories missed two
  or more days last week (`cal-week`). With water shown, the water goal missed
  three or more days of last week's seven (`water`). With a daily checklist,
  finished on four or fewer of them (`list`).
- **Macros, good ones.** Every logged day last week on target (`win-week`), or
  protein hit on all of them (`pro-win`), or calories (`cal-win`); each needs
  five days logged, or one good day would read as "1 of 1". Water or the
  checklist on six or seven days. The on-target streak reaching 7, 14, 21, 30,
  60, 90, 180 or 365, on the day it does (`streak`). Protein up five grams a
  day or more on the week before, for an "at least" goal, with four days
  logged in each week (`pro-up`).
- **Gym.** Last week's gym days against the planned week (`store.week`); with
  no planned week, against the workouts-a-week goal (`store.gymGoal`). Never
  both, which would be one week said twice. Fewer is the reminder; as many or
  more is gold, and two or more weeks of it in a row is a line of its own
  (`weeks`). With neither a plan nor a goal, seven days or more since the last
  workout (`idle`). Then weight moved: last week the most of any week, once
  there are three earlier weeks to beat (`best`), or more than the week before
  (`up`). A plan nobody has trained to yet says nothing.
- **Cardio.** By the goal's own period. A daily goal (steps, usually) counts
  last week's days: two or more missed is the reminder, six or seven hit is
  gold. A weekly goal compares last week's total, and two or more weeks met in
  a row is a line of its own; a monthly one compares last month's. More than
  the week before, in whatever the goal counts, is a good one too (`up`). A
  goal nobody has counted toward says nothing. The cardio goal is not stamped
  on a day the way the food goal is, so last week is judged against the goal
  as it stands now.

Water and the checklist stay quiet in a week with none of either recorded:
switched on and never used is not a week of misses.

**A day nobody logged is not a missed day.** `dayMacro()` returns null for a day
with no food or with a food still waiting for numbers; it ends a run and is
left out of last week's count. A reminder that fires on an empty log is worse
than none.

**One a day per tab, and never the same one twice.** A line's id carries the
day, week or month it is about (`macros/cal-week:2026-11-08`). *Got it* writes
that id and today's date into `store.lineGot`: the tab stays quiet for the rest
of the day, and that line stays away for its own period, so tomorrow brings the
next thing. A reminder holds its place until it is answered. Good news takes
turns by the day (`dailyLine()` picks by the day's number), so a good week is a
different line each morning with no *Got it* needed. Ids older than 62 days are dropped, since no line alive could still
carry one. `lineGot` does not travel in a restore (it is what this phone has
said); `lineOff` does. Settings has *Daily line: Hidden / Shown*.

It shows on today only, and never over a workout or cardio clock that is
running. It is drawn by `drawDayLine()` into the top of `#view` after the tab
has drawn itself, so no tab's own render knows about it. It reads only the log
on the phone: nothing is sent, and no AI is asked.

`sweep` holds the clock at noon on a Wednesday for these, because which lines
are due depends on the day of the week: a streak of seven lands on a Sunday,
three days of nothing logged on a Wednesday, and a suite that passes on
Tuesdays only is the stale-build lesson in another form. It checks every line beside a log that must stay quiet (two days, one
missed day, four good days, no plan, a plan never trained to, a goal never
counted toward, a running clock, a day gone by), and that the day after a *Got
it* brings the next line and not the same one. `darkcheck`'s gold pass puts both
looks on screen.

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
