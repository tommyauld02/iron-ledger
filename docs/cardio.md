# The Cardio tab

Moved word for word from `CLAUDE.md` (issue #10), which keeps the seven
rules and the index of these docs. The rules apply here too.

**Cardio has a tab of its own.** Asked for by Nygle, a tester, and placed
where Coach used to sit, between Gym and Log (Coach, when switched on, follows
it). It is the Gym tab's shape kept simple. `renderCardio()` draws it, and a
day carries `d.cardio`, a list of `{id, type, min, dist?, cal?, t}`. The types
are the owner's own names (`store.cardioTypes`), added from the picker's *+ New
type…* and taken off with its minus. Like movements, a session carries its
own name, so taking a type off the list leaves history alone.

*Start cardio* (the plate above the tabs from b98, named *Start cardio
session* for a screen reader) asks what it is, then runs a clock (`d.cardioStart`,
`d.cardioType`) that is a timestamp for the workout clock's reason. *Stop and
log it* turns it into a session (`stopCardio()`) under the same rules as the
workout clock. Over `MAX_SESSION_MS` it was forgotten, so nothing is logged,
and the bar goes *Left running* first. Under a minute it was a mis-tap, and
the app says nothing was logged. Midnight stops it on the day it started and
says so. Sessions can also be added by hand: minutes are required and say so;
miles and calories are optional. The calories are typed from the machine or a
watch. The app does not guess them, because it does not know anyone's weight
and a made-up number is the confident wrong one. *Finish cardio* is *Lock in
the day*: a *Cardio complete* card, `celebrate()`, and *Unlock*. There is no
rest timer here; it stays a Gym-tab thing.

**The goal counts what the owner chooses.** Minutes a week is the default
(the owner's call). He asked for distance and calories burned as goals too,
each daily, weekly or monthly, so `store.cardioGoal` is `{kind, period, v}`
over `CARDIO_KINDS` × `CARDIO_PERIODS`, and `cardioTotals(key, period)` sums
the day, its Sunday-first week, or its month. Switching what is counted or how
often goes to that pairing's starting number (`CARDIO_GOAL_START`) rather than
re-reading the old one, which is the unit picker's rule. The editor flips its
buttons in place, so a number being typed survives. Met, the line turns
`--hit`. On the Log tab, `cardioTrackerHtml()` draws the last eight of the
goal's own periods against a dashed goal line, grey under it and green on it
(never teal, which means *tap*), with an even number of tiles. It draws
nothing until something has been logged. Calendar colours are untouched, and a
day's title names its cardio.

**Steps are the goal's fifth choice (b92).** Asked for by the owner, who counts
steps rather than minutes, as an alternative to minutes rather than a goal of
its own: Minutes, Distance, Calories and Sessions stay exactly as they were for
everyone who uses them, and Steps sits beside them in `CARDIO_KINDS`, by the
day, week or month (10,000, 70,000 and 300,000 to start; the source is beside
`CARDIO_GOAL_START`). Five buttons go three over two (`.seg.five`), on the
Cardio tab and in Settings → You. A day's steps are the day's own number,
`d.steps` with `d.stepsAt`, not any session's, because a phone counts them all
day; so the lap has one stretch a day rather than one a session
(`cardioPeriodVals()`), and `cardioTotals()` adds `steps` and `stepDays`.
Steps are not turned into minutes or miles: that would mean guessing a
stride, the confident wrong number. While the goal counts steps, the lap has
*Enter today's steps* (*Change…* once there are some), a sheet with one box.
The number typed **replaces** the day's, since it is what the phone or watch
shows for the whole day, and the sheet says so; Save says *Steps for today:
6,240* (and *(was …)* when it replaced one) with Undo, and *Take off today's
steps* is there once there are some, with Undo too. "8,432" is 8432: a comma
in a step count is never a decimal point (`stepsFrom()`, and `pfCardioV()` in
the profile, where `num1()` would read it as one). The box shows only while the
goal counts steps, but steps can still be typed once the day's cardio is
finished, because they keep coming until midnight. A day's steps stay in the
log whatever the goal counts later; a day's title names them, the week strip
marks and counts days with steps while the goal counts them, and the Log's
tracker becomes *Steps · last 8 …* with the year's steps in its tiles. As with
the other four, past periods are drawn against the goal in force now, not one
stamped on each day. Steps travel in a backup, since they are part of the day.

**Steps from Apple Health fill in by themselves in the iPhone app (b93,
shell 1.4).** No browser can read Health, so the web app, and phones still on
shell 1.3 or older, keep typing; the page asks `shellHas("HealthSteps")`
first, so an older shell is never asked. Steps only: the owner was asked
whether workouts from Fitness or Strava should come in as cardio sessions too
and chose steps only for now (2026-11-09); that would be another shell, with
its own permission.

- **Asked once, while the goal counts steps.** A card above the lap, *Steps
  from Apple Health*, says what is read and that nothing is written or sent,
  with *Connect Apple Health* and *Not now*. Connect shows iOS's own sheet
  (read steps, share nothing), then reads and says *Apple Health filled in
  steps for 3 days*. Not now, with Undo, puts the card away for good, and the
  steps box keeps *Fill in from Apple Health* for later. The answer is
  `store.healthSteps` (`{on, at}`), this phone's own: a backup never brings it,
  since a new phone has not been asked.
- **What is read.** Each day's total as Health adds it up (an iPhone and a
  watch counting the same walk count it once, as the Health app shows),
  from the start of the eight periods the Log's tracker draws (and the period
  of the day on show) to today, at most 400 days. Health is read on opening,
  on coming back to the app and when the Cardio tab is drawn, at most once a
  minute, and only while the goal counts steps.
- **A typed number is never written over.** A day Health filled carries
  `d.stepsBy = "health"` and follows Health as its count grows. A day without
  it was typed (every b92 day looks like that) and stays as typed. The lap
  says which: *Today's steps come from Apple Health · 9:41 pm*, or *You typed
  today's steps, so Apple Health leaves them be*. In the steps box a Health
  day's box starts empty, saying *Apple Health says 6,800 so far today*, so
  Save never freezes Health's own number as a typed one; typing one replaces
  it, with Undo. A typed day offers *Use Apple Health's 7,000 instead*, with
  Undo, in place of *Take off*. *Stop filling in from Apple Health*, with
  Undo, stops the reading; the numbers so far stay.
- **Filling a day never touches its `updated`**, so a backup restored later
  still wins for that day's food and sets in `mergeInto`, and its steps fill
  in again on the next read.
- **Nothing is redrawn over something half typed.** A read that lands while a
  sheet is open, a field has focus, or the goal or a session is being edited
  changes the log and waits for the next redraw.
- **iOS never says whether reading was allowed.** A no reads exactly like a
  phone with no steps in Health. So when a read finds no steps on any day, the
  lap says *Nothing from Apple Health yet. If steps never come, check Settings
  → Health → Data Access & Devices → MNTL D&T*, rather than claiming either.
  A failed read (the phone locked, Health busy) changes nothing and is tried
  at the next look. A log that says yes on a phone iOS never asked (the log
  came over in the phone's own backup) gets the card again.

The shell's side, and what the store build needs, is in `docs/ios.md` (*Steps
from Apple Health*). `tests/native.py` checks all of the above with a stand-in
for the plugin, and `tests/darkcheck.py` the card and the lap's line in both
themes.
